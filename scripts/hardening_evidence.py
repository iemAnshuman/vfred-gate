#!/usr/bin/env python3
"""Seal the selective-hardening search and clean-rebuild evidence."""

from pathlib import Path
import argparse
import json

from vfg.controller import rederive
from vfg.manifest import atomic_json, file_digest, load_document, now

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", type=Path, default=ROOT / "runs/hardening-search/search.json")
    ap.add_argument("--selective", type=Path, default=ROOT / "runs/selective-exploratory")
    ap.add_argument("--candidate", type=Path, default=ROOT / "runs/contractfast-exploratory")
    ap.add_argument("--output", type=Path, default=ROOT / "runs/hardening-evidence")
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("hardening evidence output is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)

    search = load_document(args.search)
    selective = rederive(args.selective)
    candidate = rederive(args.candidate)
    if selective["verdict"]["verdict"] != "PASS":
        raise RuntimeError("selective build does not pass the exploratory contract")
    if candidate["verdict"]["verdict"] != "FAIL":
        raise RuntimeError("global candidate does not fail the exploratory contract")
    if search["minimal_set"] != ["ops.cpp"]:
        raise RuntimeError("unexpected minimal hardening set")
    if not search["full_exploratory_result"]["passed"]:
        raise RuntimeError("minimal set does not pass the full exploratory screening")
    if search["full_exploratory_result"]["failures"]:
        raise RuntimeError("minimal set left screening failures")

    stack = load_document(ROOT / "stacks/selective.json")
    manifest = load_document(ROOT / "build/selective-release/build-manifest.json")
    if manifest["binary_sha256"] != stack["binary_sha256"]:
        raise RuntimeError("clean selective build identity mismatch")
    launcher = manifest.get("launcher") or {}
    if launcher.get("config", {}).get("strict_sources") != ["ggml-cpu/ops.cpp"]:
        raise RuntimeError("clean selective build did not use the winning strict source")

    result = {
        "schema_version": 1,
        "generated_at": now(),
        "execution_class": "host",
        "scope": "translation-unit selective hardening on ARM64; not RVV hardware",
        "search": {
            "path": str(args.search),
            "sha256": file_digest(args.search),
            "sites": [site["name"] for site in search["sites"]],
            "minimal_set": search["minimal_set"],
            "minimal_size": search["minimal_size"],
            "ddmin_tests": len(search["ddmin_trace"]),
            "full_exploratory_failures": search["full_exploratory_result"]["failures"],
        },
        "global_candidate": {
            "bundle": str(args.candidate),
            "bundle_sha256": candidate["bundle_sha256"],
            "verdict": candidate["verdict"]["verdict"],
            "distinct_cases": candidate["verdict"]["evidence"]["distinct_cases"],
            "completed_jobs": candidate["verdict"]["evidence"]["completed_jobs"],
        },
        "selective_clean_build": {
            "bundle": str(args.selective),
            "bundle_sha256": selective["bundle_sha256"],
            "verdict": selective["verdict"]["verdict"],
            "distinct_cases": selective["verdict"]["evidence"]["distinct_cases"],
            "completed_jobs": selective["verdict"]["evidence"]["completed_jobs"],
            "binary_sha256": stack["binary_sha256"],
            "build_manifest_sha256": stack["build_manifest_sha256"],
            "strict_sources": launcher["config"]["strict_sources"],
            "candidate_flags": launcher["config"]["candidate_flags"],
        },
        "minimality": {
            "removing_ops_cpp_is_global_candidate": True,
            "global_candidate_verdict": candidate["verdict"]["verdict"],
            "reason": "the empty hardening set is the global fast build, which fails the same contract",
        },
        "clean_rebuild": True,
        "host_cost_secondary": None,
        "limitation": (
            "Sites are translation units, not individual reduction instructions. The clean build "
            "uses a compiler launcher to apply fast contraction everywhere except ggml-cpu/ops.cpp."
        ),
    }
    cost_path = ROOT / "runs/hardening-cost/cost.json"
    if cost_path.exists():
        cost = load_document(cost_path)
        result["host_cost_secondary"] = {
            "path": str(cost_path),
            "sha256": file_digest(cost_path),
            "relative_median": cost["relative_median"],
            "output_matches": cost["output_matches_global_strict"],
            "interpretation": "host timing only; differences are small and not an RVV cost conclusion",
        }
    atomic_json(out / "manifest.json", result)
    print(
        json.dumps(
            {
                "minimal_set": result["search"]["minimal_set"],
                "selective_verdict": result["selective_clean_build"]["verdict"],
                "candidate_verdict": result["global_candidate"]["verdict"],
                "jobs": result["selective_clean_build"]["completed_jobs"],
            }
        )
    )


if __name__ == "__main__":
    main()
