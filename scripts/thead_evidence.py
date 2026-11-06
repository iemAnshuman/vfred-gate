#!/usr/bin/env python3
"""Summarise the Rostam sven0 (RVV 0.7.1 / XTheadVector) board run.

Reads the raw job log, checks the five repetitions, and re-derives legal-envelope
containment for every dumped record. Writes manifest.json next to the log.
"""

from pathlib import Path
import argparse
import json
import re

from vfg.legal import chunk_envelope, contains, seed_root_envelope, value_of
from vfg.manifest import atomic_json, file_digest, now

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/completion/rostam-thead"
SOURCES = [ROOT / "microbench/rvv/thead/probe.c", ROOT / "microbench/rvv/thead/reduce.S"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=EVIDENCE / "run2.txt")
    args = ap.parse_args()
    text = args.log.read_text()

    hashes = {name: digest for digest, name in re.findall(r"^([0-9a-f]{64})  (\S+)$", text, re.M)}
    for source in SOURCES:
        if hashes.get(source.name) != file_digest(source):
            raise RuntimeError(f"{source.name} differs from the source that ran on the board")

    reps = re.findall(r"^rep(\d) exit=(\d+) ([0-9a-f]{64})", text, re.M)
    totals = re.search(
        r"^trials=(\d+) invocations=(\d+) ordered_equals_scalar=(\d+) unordered_differs=(\d+)$", text, re.M
    )
    vlmax = int(re.search(r"^vlmax_e32m1=(\d+)$", text, re.M).group(1))
    distinct_dumps = int(re.search(r"^(\d+)$", text, re.M).group(1))
    job = re.search(r"^SLURM_JOB_ID=(\d+)$", text, re.M).group(1)

    records = [line.split() for line in text.splitlines() if line.startswith("rec ")]
    ordered_ok = differs = inside_leaf = inside_root = 0
    max_support = 0
    for rec in records:
        n = int(rec[2])
        scalar, ordered, unordered = (int(v, 16) for v in rec[3:6])
        operands = [value_of(int(v, 16)) for v in rec[6 : 6 + n]]
        ordered_ok += scalar == ordered
        differs += unordered != ordered
        leaf = chunk_envelope(0.0, operands, chunk_size=vlmax)
        max_support = max(max_support, len(leaf["support"]))
        inside_leaf += contains(leaf, unordered)
        inside_root += contains(seed_root_envelope(0.0, operands, chunk_size=vlmax), unordered)

    manifest = {
        "recorded_at": now(),
        "execution_class": "hardware",
        "node": "sven0.rostam.cct.lsu.edu",
        "slurm_job_id": int(job),
        "cpu": {"mvendorid": "0x5b7", "device_tree": "sophgo,mango", "vector_extension": "RVV 0.7.1 (XTheadVector)"},
        "rvv_1_0": False,
        "encoding": "hand-encoded .word; reduction words match LLVM vfredusum.vs/vfredosum.vs",
        "log": {"path": args.log.name, "sha256": file_digest(args.log)},
        "sources": {s.name: file_digest(s) for s in SOURCES},
        "vlmax_e32m1": vlmax,
        "repetitions": {
            "count": len(reps),
            "all_exit_zero": all(code == "0" for _, code, _ in reps),
            "identical_output": len({digest for _, _, digest in reps}) == 1,
            "identical_dumps": distinct_dumps == 1,
        },
        "search": {
            "trials": int(totals.group(1)),
            "invocations": int(totals.group(2)),
            "ordered_equals_scalar": int(totals.group(3)),
            "unordered_differs": int(totals.group(4)),
        },
        "envelope": {
            "records": len(records),
            "ordered_equals_scalar": ordered_ok,
            "unordered_differs": differs,
            "inside_leaf_model": inside_leaf,
            "inside_seed_root_model": inside_root,
            "max_support": max_support,
        },
    }
    atomic_json(EVIDENCE / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
