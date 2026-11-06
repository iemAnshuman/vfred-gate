#!/usr/bin/env python3
"""Measure host wall time for native, global-fast and selective builds.

This is a host cost study, not RVV performance evidence. Every run is a fresh process.
"""

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import time

from vfg.manifest import atomic_json, file_digest, load_document, now

ROOT = Path(__file__).resolve().parents[1]


def load_requests(bundle, case_ids):
    bundle = Path(bundle)
    inputs = load_document(bundle / "inputs.json")
    run = load_document(bundle / "run.json")
    cases = {case["id"]: case for case in inputs["selected_cases"]}
    requests = []
    for case_id in case_ids:
        job = next(
            job
            for job in run["jobs"]
            if job["case_id"] == case_id and job["role"] == "candidate" and job["repetition"] == 0
        )
        request = load_document(bundle / job["path"] / "request.json")
        request["max_tokens"] = 128
        request["context"] = 512
        requests.append({"case_id": case_id, "request": request, "category": cases[case_id]["category"]})
    return requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=ROOT / "runs/contractfast-exploratory")
    ap.add_argument("--output", type=Path, default=ROOT / "runs/hardening-cost")
    ap.add_argument("--repetitions", type=int, default=5)
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("cost output is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)

    binaries = {
        "global_strict": ROOT / "build/host-release/runner/vfg-llama-runner",
        "candidate_fast": ROOT / "build/contract-release/runner/vfg-llama-runner",
        "selective_strict_ops": ROOT / "build/selective-release/runner/vfg-llama-runner",
    }
    for name, path in binaries.items():
        if not path.exists():
            raise RuntimeError(f"missing binary: {name}")
    case_ids = ["c001", "c002", "c003", "c004", "c007", "c008", "c009", "c010"]
    cases = load_requests(args.bundle, case_ids)

    work = out / "runs"
    work.mkdir()
    samples = []
    for repetition in range(args.repetitions):
        for case in cases:
            for name, binary in binaries.items():
                directory = work / f"{name}-{case['case_id']}-r{repetition}"
                request_path = directory / "request.json"
                directory.mkdir(parents=True)
                request_path.write_text(json.dumps(case["request"]))
                output = directory / "output"
                started = time.monotonic()
                proc = subprocess.run([str(binary), str(request_path), str(output)], capture_output=True, text=True)
                elapsed = time.monotonic() - started
                record = {
                    "binary": name,
                    "case_id": case["case_id"],
                    "repetition": repetition,
                    "returncode": proc.returncode,
                    "wall_seconds": elapsed,
                }
                if proc.returncode:
                    record["error"] = proc.stderr[-500:]
                else:
                    result = json.loads((output / "result.json").read_text())
                    record.update(
                        {
                            "load_seconds": result["load_seconds"],
                            "prefill_seconds": result["prefill_seconds"],
                            "generation_seconds": result["generation_seconds"],
                            "selected_tokens": result["selected_tokens"],
                            "logits_sha256": result["logits_sha256"],
                        }
                    )
                samples.append(record)
                if proc.returncode:
                    raise RuntimeError(f"run failed: {name}/{case['case_id']}: {proc.stderr[-500:]}")

    summary = {}
    for name in binaries:
        rows = [row for row in samples if row["binary"] == name]
        summary[name] = {
            "runs": len(rows),
            "wall_median": statistics.median(row["wall_seconds"] for row in rows),
            "wall_mean": statistics.mean(row["wall_seconds"] for row in rows),
            "generation_median": statistics.median(row["generation_seconds"] for row in rows),
            "prefill_median": statistics.median(row["prefill_seconds"] for row in rows),
            "load_median": statistics.median(row["load_seconds"] for row in rows),
        }

    baseline_tokens = {
        row["case_id"]: row["selected_tokens"]
        for row in samples
        if row["binary"] == "global_strict" and row["repetition"] == 0
    }
    output_matches = {}
    for name in binaries:
        output_matches[name] = all(
            row["selected_tokens"] == baseline_tokens[row["case_id"]]
            for row in samples
            if row["binary"] == name
        )

    result = {
        "schema_version": 1,
        "generated_at": now(),
        "execution_class": "host",
        "workload": {
            "cases": case_ids,
            "repetitions": args.repetitions,
            "max_tokens": 128,
            "context": 512,
        },
        "binaries": {
            name: {"path": str(path), "sha256": file_digest(path)} for name, path in binaries.items()
        },
        "summary": summary,
        "output_matches_global_strict": output_matches,
        "relative_median": {
            "selective_vs_global_strict": summary["selective_strict_ops"]["wall_median"]
            / summary["global_strict"]["wall_median"],
            "selective_vs_candidate_fast": summary["selective_strict_ops"]["wall_median"]
            / summary["candidate_fast"]["wall_median"],
            "candidate_fast_vs_global_strict": summary["candidate_fast"]["wall_median"]
            / summary["global_strict"]["wall_median"],
        },
        "limitations": [
            "ARM64 macOS host timing, not an RVV board measurement.",
            "This is a translation-unit hardening analogue, not an instruction-level reduction toggle.",
            "Model load and prompt prefill are included in wall time; generation medians are reported separately.",
            "The candidate and selective builds differ only in FP-contraction flags on the selected translation unit.",
        ],
    }
    atomic_json(out / "cost.json", result)
    print(json.dumps({"summary": summary, "relative": result["relative_median"], "match": output_matches}))


if __name__ == "__main__":
    main()
