#!/usr/bin/env python3
"""Build the legal reduction envelope for the recorded QEMU probe and validate it."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess

from vfg.legal import bits_of, chunk_envelope, seed_root_envelope, summarize, value_of

ROOT = Path(__file__).resolve().parents[1]


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dbits(value):
    return struct.pack("<d", value).hex()


def load_records(path):
    data = json.loads(Path(path).read_text())
    records = [row for row in data["records"] if row["repetition"] == 0]
    return data, records


def operands(row):
    return [struct.unpack("<f", int(bits).to_bytes(4, "little"))[0] for bits in row["input_bits"]]


def build_sampler(output):
    cxx = shutil.which("c++") or shutil.which("clang++")
    if not cxx:
        raise RuntimeError("no C++ compiler")
    command = [
        cxx,
        "-O2",
        "-std=c++17",
        "-fno-fast-math",
        "-ffp-contract=off",
        str(ROOT / "microbench/envelope/sampler.cpp"),
        "-o",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return command, cxx


def sampler_support(binary, seed, values):
    request = [f"seed {bits_of(seed):08x}", f"n {len(values)}"]
    request.extend(f"{bits_of(v):08x}" for v in values)
    text = "\n".join(request) + "\n"
    proc = subprocess.run([str(binary), "/dev/stdin"], input=text, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    data = json.loads(proc.stdout)
    return {
        struct.unpack(">d", int(item, 16).to_bytes(8, "big"))[0] for item in data["values"]
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, default=ROOT / "runs/mechanism/stdout.json")
    ap.add_argument("--search-records", type=Path, default=ROOT / "runs/mechanism-search/stdout.json")
    ap.add_argument("--probe-manifest", type=Path, default=ROOT / "runs/mechanism/manifest.json")
    ap.add_argument("--output", type=Path, default=ROOT / "runs/legal-envelope")
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("envelope output is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)

    data, rows = load_records(args.records)
    sampler = out / "envelope-sampler"
    command, cxx = build_sampler(sampler)

    records = []
    independent = []
    all_ordered = True
    all_contained = True
    for row in rows:
        n = row["n"]
        if n == 0:
            continue
        values = operands(row)
        primary = chunk_envelope(0.0, values, chunk_size=data["vlmax"])
        conservative = seed_root_envelope(0.0, values, chunk_size=data["vlmax"])
        primary_ordered = summarize(primary, row["ordered_bits"])
        primary_unordered = summarize(primary, row["unordered_bits"])
        conservative_ordered = summarize(conservative, row["ordered_bits"])
        conservative_unordered = summarize(conservative, row["unordered_bits"])
        observed_same = row["ordered_bits"] == row["unordered_bits"]
        ordered_matches_scalar = row["ordered_bits"] == row["scalar_bits"]
        all_ordered &= ordered_matches_scalar
        all_contained &= primary_ordered["contained"] and primary_unordered["contained"]
        item = {
            "fixture": row["fixture"],
            "n": n,
            "chunks": row["chunks"],
            "input_sha256": hashlib.sha256(
                b"".join(int(bits).to_bytes(4, "little") for bits in row["input_bits"])
            ).hexdigest(),
            "observed": {
                "ordered_bits": row["ordered_bits"],
                "unordered_bits": row["unordered_bits"],
                "scalar_bits": row["scalar_bits"],
                "ordered_matches_scalar": ordered_matches_scalar,
                "policies_agree": observed_same,
                "ordered_value": value_of(row["ordered_bits"]),
                "unordered_value": value_of(row["unordered_bits"]),
            },
            "primary": {
                "ordered": primary_ordered,
                "unordered": primary_unordered,
            },
            "conservative": {
                "ordered": conservative_ordered,
                "unordered": conservative_unordered,
            },
        }
        records.append(item)
        if n <= data["vlmax"]:
            python_support = set(primary["support"])
            cpp_support = sampler_support(sampler, 0.0, values)
            independent.append(
                {
                    "fixture": row["fixture"],
                    "n": n,
                    "python_size": len(python_support),
                    "cpp_size": len(cpp_support),
                    "equal": python_support == cpp_support,
                    "python_sha256": hashlib.sha256(
                        b"".join(bytes.fromhex(dbits(v)) for v in sorted(python_support))
                    ).hexdigest(),
                    "cpp_sha256": hashlib.sha256(
                        b"".join(bytes.fromhex(dbits(v)) for v in sorted(cpp_support))
                    ).hexdigest(),
                }
            )

    if not all_ordered:
        raise RuntimeError("the ordered reduction does not match the scalar left fold")
    if not all_contained:
        raise RuntimeError("an observed QEMU value is outside the primary legal envelope")
    if not all(item["equal"] for item in independent):
        raise RuntimeError("the independent sampler disagrees with the Python envelope")

    controls = []
    chosen = next((item for item in records if item["primary"]["ordered"]["support_size"] > 1), None)
    if chosen is None:
        raise RuntimeError("no record has more than one legal result; controls are not meaningful")
    values = operands(next(row for row in rows if row["fixture"] == chosen["fixture"] and row["n"] == chosen["n"]))
    observed = chosen["observed"]["ordered_bits"]
    wrong_seed = chunk_envelope(10.0, values, chunk_size=data["vlmax"])
    controls.append(
        {
            "control": "wrong scalar seed",
            "observed_bits": observed,
            "observed_in_wrong_seed_envelope": observed in {bits_of(v) for v in wrong_seed["support"]},
            "expected": False,
        }
    )
    maximum = chosen["primary"]["ordered"]["interval"]["maximum"]
    outside = math.nextafter(maximum, math.inf) if math.isfinite(maximum) else None
    primary_support = set(chunk_envelope(0.0, values, chunk_size=data["vlmax"])["support"])
    controls.append(
        {
            "control": "next float above the legal interval",
            "value": outside,
            "inside": outside in primary_support if outside is not None else None,
            "expected": False,
        }
    )
    if controls[0]["observed_in_wrong_seed_envelope"] or controls[1].get("inside"):
        raise RuntimeError("negative control was not rejected")

    random_samples = []
    search_sha = None
    if args.search_records.exists():
        search = json.loads(args.search_records.read_text())
        search_sha = file_sha(args.search_records)
        for sample in search.get("samples", []):
            values = [
                struct.unpack("<f", int(bits).to_bytes(4, "little"))[0]
                for bits in sample["input_bits"]
            ]
            try:
                envelope = chunk_envelope(0.0, values, chunk_size=data["vlmax"])
            except Exception as exc:
                random_samples.append({"trial": sample["trial"], "n": sample["n"], "error": str(exc)})
                continue
            result = summarize(envelope, sample["ordered_bits"])
            random_samples.append(
                {
                    "trial": sample["trial"],
                    "n": sample["n"],
                    "support_size": result["support_size"],
                    "contained": result["contained"],
                    "other_legal_examples": result["other_legal_examples"],
                    "interval": result["interval"],
                    "policies_agree": sample["ordered_bits"] == sample["unordered_bits"],
                }
            )
    if any(not item.get("contained", False) for item in random_samples):
        raise RuntimeError("a random sample is outside the legal envelope")

    summary = {
        "records": len(records),
        "independent_records": len(independent),
        "independent_equal": all(item["equal"] for item in independent),
        "all_observed_contained": all_contained,
        "ordered_matches_scalar": all_ordered,
        "policies_agree_on_qemu": all(item["observed"]["policies_agree"] for item in records),
        "records_with_one_legal_result": sum(
            item["primary"]["ordered"]["support_size"] == 1 for item in records
        ),
        "maximum_support_size": max(item["primary"]["ordered"]["support_size"] for item in records),
        "records_with_other_legal_examples": sum(
            bool(item["primary"]["ordered"]["other_legal_examples"]) for item in records
        ),
        "random_samples": len(random_samples),
        "random_samples_with_multiple_results": sum(
            item.get("support_size", 0) > 1 for item in random_samples
        ),
        "random_maximum_support_size": max(
            (item.get("support_size", 0) for item in random_samples), default=0
        ),
    }
    envelope = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_records": str(args.records),
        "source_records_sha256": file_sha(args.records),
        "model": {
            "name": "rve-1.0-unordered-sum",
            "leaves": "scalar seed plus active elements",
            "precision_set": [32, 64],
            "rounding": "round-to-nearest, ties-to-even",
            "chunking": "fixed by vl and VLMAX; the scalar accumulator carries across chunks",
            "primary": "seed and elements are leaves",
            "conservative": "seed added once at the root",
        },
        "summary": summary,
        "records": records,
        "random_samples": random_samples,
        "controls": controls,
        "independent_sampler": independent,
        "limitations": [
            "Sampling a model of the specification is not a proof of every permitted result.",
            "Only binary32 and binary64 intermediate rounding are modelled.",
            "Only round-to-nearest, ties-to-even is modelled.",
            "QEMU returned the same bits for both policies on every recorded case, so no second implementation's value is exercised.",
            "The independent sampler shares the mathematical model; it is an implementation check, not a second hardware implementation.",
        ],
    }
    (out / "envelope.json").write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_class": "emulator",
        "qemu_probe_manifest": str(args.probe_manifest),
        "qemu_probe_manifest_sha256": file_sha(args.probe_manifest),
        "search_records": str(args.search_records),
        "search_records_sha256": search_sha,
        "sampler_build_command": command,
        "compiler_version": subprocess.check_output([cxx, "--version"], text=True),
        "sources": {
            "src/vfg/legal/envelope.py": file_sha(ROOT / "src/vfg/legal/envelope.py"),
            "microbench/envelope/sampler.cpp": file_sha(ROOT / "microbench/envelope/sampler.cpp"),
            "scripts/envelope_evidence.py": file_sha(ROOT / "scripts/envelope_evidence.py"),
        },
        "outputs": {
            "envelope.json": file_sha(out / "envelope.json"),
        },
        "summary": summary,
        "physical_board_gate": "blocked",
        "scope": "QEMU RVV probe values; not a model qualification and not a second board",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
