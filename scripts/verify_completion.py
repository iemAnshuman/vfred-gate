#!/usr/bin/env python3
"""Recheck the completion ledger and the new research receipts."""

import argparse
import json
from pathlib import Path

from vfg.controller import rederive
from vfg.manifest import file_digest, load_document
from vfg.progress import check_progress
from vfg.replay.localise import verify_localisation

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=ROOT / "docs/progress.yaml")
    ap.add_argument("--min-points", type=int, default=71)
    args = ap.parse_args()
    result = check_progress(args.ledger)
    checks = {"ledger": True}

    envelope_path = ROOT / "runs/legal-envelope/envelope.json"
    envelope_manifest = ROOT / "runs/legal-envelope/manifest.json"
    if not envelope_path.exists():
        raise SystemExit("missing legal envelope evidence")
    envelope = load_document(envelope_path)
    manifest = load_document(envelope_manifest)
    if file_digest(envelope_path) != manifest["outputs"]["envelope.json"]:
        raise SystemExit("legal envelope hash mismatch")
    if not envelope["summary"]["all_observed_contained"] or not envelope["summary"]["independent_equal"]:
        raise SystemExit("legal envelope checks failed")
    checks["legal_envelope"] = True

    study_path = ROOT / "runs/canary-study/study.json"
    if not study_path.exists():
        raise SystemExit("missing canary study")
    study = load_document(study_path)
    primary = study["selection"]["sequence_failure"]
    if primary["rule"]["threshold"] != 0.10355377197265625:
        raise SystemExit("frozen canary threshold changed")
    if primary["holdout"]["recall"] is None:
        raise SystemExit("canary recall is undefined")
    checks["canary"] = True

    hardening_path = ROOT / "runs/hardening-evidence/manifest.json"
    if not hardening_path.exists():
        raise SystemExit("missing hardening evidence")
    hardening = load_document(hardening_path)
    if hardening["search"]["minimal_set"] != ["ops.cpp"]:
        raise SystemExit("unexpected minimal hardening set")
    checks["hardening"] = True

    selective = rederive(ROOT / "runs/selective-exploratory")["verdict"]
    if selective["verdict"] != "PASS" or selective["evidence"]["completed_jobs"] != 320:
        raise SystemExit("selective clean build did not pass")
    checks["selective_qualification"] = True

    localisation = verify_localisation(ROOT / "runs/seeded-operator")
    if not localisation["baseline_restored"]:
        raise SystemExit("seeded localisation did not restore the baseline")
    checks["seeded_localisation"] = True

    output = {
        "accepted_points": result["accepted_points"],
        "unearned_points": result["unearned_points"],
        "accepted_items": result["accepted_items"],
        "blocked_or_deferred": result["blocked_or_deferred"],
        "checks": checks,
    }
    print(json.dumps(output, indent=2))
    return 0 if result["accepted_points"] >= args.min_points else 3


if __name__ == "__main__":
    raise SystemExit(main())
