#!/usr/bin/env python3
"""Search a minimal translation-unit hardening set for a failing candidate build.

The search uses mixed-object variants: selected translation units come from the strict
build, the rest from the candidate build. This is a screening build, not the final clean
rebuild. The winning set is rebuilt from source in the accompanying clean-build step.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time

from vfg.harden import ddmin
from vfg.manifest import atomic_json, load_document, now

ROOT = Path(__file__).resolve().parents[1]

SITES = [
    {"name": "ops.cpp", "suffix": "ggml-cpu/ops.cpp", "archive": "llama/ggml/src/libggml-cpu.a"},
    {"name": "ggml-cpu.c", "suffix": "ggml-cpu/ggml-cpu.c", "archive": "llama/ggml/src/libggml-cpu.a"},
    {"name": "vec.cpp", "suffix": "ggml-cpu/vec.cpp", "archive": "llama/ggml/src/libggml-cpu.a"},
    {"name": "quants.c", "suffix": "ggml-cpu/quants.c", "archive": "llama/ggml/src/libggml-cpu.a"},
    {"name": "repack.cpp", "suffix": "ggml-cpu/repack.cpp", "archive": "llama/ggml/src/libggml-cpu.a"},
    {"name": "binary-ops.cpp", "suffix": "ggml-cpu/binary-ops.cpp", "archive": "llama/ggml/src/libggml-cpu.a"},
    {"name": "unary-ops.cpp", "suffix": "ggml-cpu/unary-ops.cpp", "archive": "llama/ggml/src/libggml-cpu.a"},
    {"name": "ggml.c", "suffix": "ggml/src/ggml.c", "archive": "llama/ggml/src/libggml-base.a"},
    {"name": "ggml-quants.c", "suffix": "ggml/src/ggml-quants.c", "archive": "llama/ggml/src/libggml-base.a"},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_command(entry):
    command = shlex.split(entry["command"])
    filtered = []
    skip = False
    for index, token in enumerate(command):
        if skip:
            skip = False
            continue
        if token in ("-MD", "-MT", "-MF"):
            skip = True
            continue
        filtered.append(token)
    if "-o" not in filtered:
        raise RuntimeError("compile command has no output")
    return filtered


def discover_sites(build):
    cc = json.loads((build / "compile_commands.json").read_text())
    found = []
    for spec in SITES:
        matches = [entry for entry in cc if entry["file"].endswith(spec["suffix"])]
        if len(matches) != 1:
            continue
        entry = matches[0]
        found.append(
            {
                **spec,
                "source": entry["file"],
                "object": entry["output"],
                "directory": entry["directory"],
                "compile_command": compile_command(entry),
            }
        )
    return found


def precompile_strict(sites, output):
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for site in sites:
        command = list(site["compile_command"])
        index = command.index("-o")
        target = output / (site["name"] + ".o")
        command[index + 1] = str(target)
        command.extend(["-ffp-contract=off", "-fno-fast-math"])
        started = time.monotonic()
        proc = subprocess.run(command, cwd=site["directory"], capture_output=True, text=True)
        results.append(
            {
                "site": site["name"],
                "command": command,
                "returncode": proc.returncode,
                "seconds": time.monotonic() - started,
                "object_sha256": sha(target) if proc.returncode == 0 else None,
                "stderr": proc.stderr[-500:],
            }
        )
        if proc.returncode:
            raise RuntimeError(f"strict compile failed for {site['name']}")
    return results


def clone_build(base, destination):
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-Rc", str(base), str(destination)], check=True)
    return destination


def link_variant(variant):
    commands = subprocess.check_output(
        ["ninja", "-C", str(variant), "-t", "commands", "vfg-llama-runner"], text=True
    ).splitlines()
    link = commands[-1]
    if link.startswith(": && "):
        link = link[len(": && ") :]
    proc = subprocess.run(link, shell=True, cwd=variant, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr[-2000:])
    binary = variant / "runner/vfg-llama-runner"
    return binary, link


def build_variant(base, strict_dir, sites, subset, destination):
    variant = clone_build(base, destination)
    for site in subset:
        archive = variant / site["archive"]
        obj = strict_dir / (site["name"] + ".o")
        subprocess.run(["ar", "r", str(archive), str(obj)], cwd=strict_dir, check=True, capture_output=True)
        subprocess.run(["ranlib", str(archive)], check=True, capture_output=True)
    binary, link = link_variant(variant)
    return {
        "binary": str(binary),
        "binary_sha256": sha(binary),
        "link_command": link,
        "sites": [site["name"] for site in subset],
    }


def load_bundle(root):
    root = Path(root)
    inputs = load_document(root / "inputs.json")
    run = load_document(root / "run.json")
    cases = []
    for case in inputs["selected_cases"]:
        jobs = {
            role: next(
                job
                for job in run["jobs"]
                if job["case_id"] == case["id"]
                and job["role"] == role
                and job["mode"] == "free_run"
                and job["repetition"] == 0
            )
            for role in ("baseline", "candidate")
        }
        cases.append(
            {
                "case_id": case["id"],
                "baseline_tokens": load_document(root / jobs["baseline"]["path"] / "output/result.json")[
                    "selected_tokens"
                ],
                "request": load_document(root / jobs["candidate"]["path"] / "request.json"),
            }
        )
    return cases


def screen(binary, cases, workdir):
    failures = []
    records = []
    for case in cases:
        case_dir = Path(workdir) / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        request = case_dir / "request.json"
        request.write_text(json.dumps(case["request"]))
        output = case_dir / "output"
        started = time.monotonic()
        proc = subprocess.run([str(binary), str(request), str(output)], capture_output=True, text=True)
        record = {
            "case_id": case["case_id"],
            "returncode": proc.returncode,
            "seconds": time.monotonic() - started,
        }
        if proc.returncode:
            record["error"] = proc.stderr[-500:]
            failures.append(case["case_id"])
        else:
            result = json.loads((output / "result.json").read_text())
            record["first_divergence"] = next(
                (
                    index
                    for index, (left, right) in enumerate(
                        zip(case["baseline_tokens"], result["selected_tokens"])
                    )
                    if left != right
                ),
                None,
            )
            if record["first_divergence"] is not None or len(result["selected_tokens"]) != len(
                case["baseline_tokens"]
            ):
                failures.append(case["case_id"])
        records.append(record)
    return {"passed": not failures, "failures": failures, "records": records}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-build", type=Path, default=ROOT / "build/contract-release")
    ap.add_argument("--strict-build", type=Path, default=ROOT / "build/host-release")
    ap.add_argument("--qualification", type=Path, default=ROOT / "runs/contractfast-exploratory")
    ap.add_argument("--screening", type=Path, default=ROOT / "runs/contractfast-smoke")
    ap.add_argument("--output", type=Path, default=ROOT / "runs/hardening-search")
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("hardening search output is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)

    base = args.base_build.resolve()
    sites = discover_sites(base)
    strict_dir = out / "strict-objects"
    compile_records = precompile_strict(sites, strict_dir)
    screening_cases = load_bundle(args.screening)
    full_cases = load_bundle(args.qualification)
    counter = {"value": 0}

    def test(subset):
        counter["value"] += 1
        name = "v%03d" % counter["value"]
        variant = build_variant(base, strict_dir, sites, subset, out / "variants" / name)
        result = screen(Path(variant["binary"]), screening_cases, out / "screens" / name)
        return result["passed"]

    full_set = [site for site in sites]
    if not test(full_set):
        raise RuntimeError("the full hardening set does not restore the screening contract")
    minimal, trace = ddmin(full_set, test)
    minimal_names = [site["name"] for site in minimal]

    # Validate the minimal set against the screening set and every exploratory case.
    final = build_variant(base, strict_dir, sites, minimal, out / "final-screening")
    final_screening = screen(Path(final["binary"]), screening_cases, out / "final-screening-cases")
    full_result = screen(Path(final["binary"]), full_cases, out / "full-screening")

    result = {
        "schema_version": 1,
        "generated_at": now(),
        "execution_class": "host",
        "scope": "translation-unit hardening search on a host candidate build",
        "base_build": str(base),
        "base_binary_sha256": sha(base / "runner/vfg-llama-runner"),
        "strict_build": str(args.strict_build.resolve()),
        "sites": [
            {
                "name": site["name"],
                "source": site["source"],
                "object": site["object"],
                "archive": site["archive"],
                "strict_object_sha256": record["object_sha256"],
            }
            for site, record in zip(sites, compile_records)
        ],
        "screening_cases": [case["case_id"] for case in screening_cases],
        "screening_result": final_screening,
        "full_exploratory_result": full_result,
        "minimal_set": minimal_names,
        "minimal_size": len(minimal_names),
        "ddmin_trace": trace,
        "variants": counter["value"],
        "limitation": (
            "Mixed-object screening build. The winning set is rebuilt from source in the "
            "clean-build evidence step; these object substitutions are not a clean rebuild."
        ),
    }
    atomic_json(out / "search.json", result)
    print(
        json.dumps(
            {
                "minimal_set": minimal_names,
                "screening_failures": full_result["failures"],
                "variants": counter["value"],
                "trace_tests": len(trace),
            }
        )
    )


if __name__ == "__main__":
    main()
