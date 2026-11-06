#!/usr/bin/env python3
"""Freeze the completion ledger from current, checked evidence."""

from pathlib import Path
import argparse
import json
import os
import shutil
import xml.etree.ElementTree as ET

from vfg.manifest import atomic_json, file_digest, load_document, now
from vfg.progress import WEIGHTS, check_progress

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVIDENCE = ROOT / "evidence/completion"


def tests(xml, claim, fragments):
    tree = ET.parse(xml)
    cases = tree.findall(".//testcase")
    if any(c.find("failure") is not None or c.find("error") is not None or c.find("skipped") is not None for c in cases):
        raise RuntimeError("pytest receipt contains a failed or skipped test")
    names = sorted(c.get("classname") + "." + c.get("name") for c in cases)
    selected = [name for name in names if any(fragment in name for fragment in fragments)]
    if not selected:
        raise RuntimeError("no tests match " + repr(fragments))
    return {
        "path": os.path.relpath(Path(xml), DOCS),
        "sha256": file_digest(xml),
        "kind": "pytest",
        "claim": claim,
        "tests": selected,
    }


def file_evidence(path, claim):
    path = Path(path).resolve()
    return {
        "path": os.path.relpath(path, DOCS),
        "sha256": file_digest(path),
        "kind": "file",
        "claim": claim,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", type=Path, default=ROOT / "runs/validation")
    ap.add_argument("--output", type=Path, default=DOCS / "progress.yaml")
    args = ap.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    pytest_xml = EVIDENCE / "pytest.xml"
    shutil.copyfile(args.validation / "pytest.xml", pytest_xml)
    shutil.copyfile(args.validation / "receipt.json", EVIDENCE / "receipt.json")
    receipt = load_document(EVIDENCE / "receipt.json")
    if not receipt.get("source_unchanged_during_validation"):
        raise RuntimeError("validation source changed during the run")
    if any(check["returncode"] for check in receipt["checks"]):
        raise RuntimeError("validation contains a failed check")

    mapping = {
        "W0.host": [tests(pytest_xml, "W0.host tests", ["test_host_reduction_mechanism"])],
        "W0.compile": [tests(pytest_xml, "W0.compile tests", ["test_real_elf_maps_both_policies"])],
        "W0.emulator": [tests(pytest_xml, "W0.emulator tests", ["test_rvv_execution_evidence"])],
        "W0.board": [
            tests(pytest_xml, "W0.board tests", ["test_thead_board_evidence"]),
            file_evidence(ROOT / "evidence/completion/rostam-thead/manifest.json", "sven0 RVV 0.7.1 board mechanism evidence"),
        ],
        "W1.schemas": [tests(pytest_xml, "W1.schemas tests", ["tests.unit.test_manifest."])],
        "W1.artifacts": [tests(pytest_xml, "W1.artifacts tests", ["tests.unit.test_store."])],
        "W1.build": [
            tests(pytest_xml, "W1.build tests", ["test_clean_build_metadata"]),
            file_evidence(ROOT / "runs/build-reproducibility.json", "fresh build comparison"),
        ],
        "W1.execute": [tests(pytest_xml, "W1.execute tests", ["tests.unit.test_execute."])],
        "W2.scan": [
            tests(pytest_xml, "W2.scan tests", ["test_static_zero_one_multiple_sites"]),
            tests(pytest_xml, "W2.scan invalid tests", ["test_invalid_elf"]),
        ],
        "W3.native": [tests(pytest_xml, "W3.native tests", ["tests.integration.test_runner."])],
        "W4.metrics": [tests(pytest_xml, "W4.metrics tests", ["tests.unit.test_metrics."])],
        "W4.verdicts": [tests(pytest_xml, "W4.verdicts tests", ["tests.integration.test_controller."])],
        "W4.end_to_end": [
            tests(pytest_xml, "W4.end_to_end tests", ["test_confirmation_and_compiler_comparison"]),
            {
                "path": "../runs/self-check/bundle.json",
                "sha256": file_digest(ROOT / "runs/self-check/bundle.json"),
                "kind": "qualification",
                "claim": "160 actual self-check executions",
                "verdict": "PASS",
                "minimum_cases": 16,
            },
            {
                "path": "../runs/native-comparison/bundle.json",
                "sha256": file_digest(ROOT / "runs/native-comparison/bundle.json"),
                "kind": "qualification",
                "claim": "320 compiler comparison executions",
                "verdict": load_document(ROOT / "runs/native-comparison/verdict.json")["verdict"],
                "minimum_cases": 16,
            },
        ],
        "W5.replay": [tests(pytest_xml, "W5.replay tests", ["test_seeded_replay_shared_history"])],
        "W5.capture": [
            tests(pytest_xml, "W5.capture tests", ["test_layer_capture_restoration"]),
            tests(pytest_xml, "W5.capture strides tests", ["test_production_capture_strided_view"]),
        ],
        "W5.seeded": [
            tests(pytest_xml, "W5.seeded tests", ["test_seeded_operator_and_restoration"]),
            {
                "path": "../runs/seeded-operator/bundle.json",
                "sha256": file_digest(ROOT / "runs/seeded-operator/bundle.json"),
                "kind": "localisation",
                "claim": "operator seeded localisation",
            },
        ],
        "W6.pilot": [
            tests(pytest_xml, "W6.pilot tests", ["tests.unit.test_corpus."]),
            file_evidence(ROOT / "corpora/pilot-v1.manifest.json", "frozen pilot identity"),
        ],
        "W6.prediction": [
            tests(pytest_xml, "W6.prediction tests", ["test_canary_holdout_study"]),
            file_evidence(ROOT / "runs/canary-study/study.json", "frozen holdout recall and cost"),
        ],
        "W7.replay": [
            tests(pytest_xml, "W7.replay tests", ["test_legal_envelope_evidence"]),
            file_evidence(ROOT / "runs/legal-envelope/manifest.json", "legal envelope evidence"),
        ],
        "W8.search": [
            tests(pytest_xml, "W8.search tests", ["test_selective_hardening_evidence"]),
            file_evidence(ROOT / "runs/hardening-evidence/manifest.json", "selective hardening evidence"),
        ],
        "W9.docs": [
            tests(pytest_xml, "W9.docs tests", ["test_detached_offline_bundle"]),
            file_evidence(ROOT / "docs/final-report.md", "final report"),
            file_evidence(ROOT / "README.md", "project overview"),
            file_evidence(ROOT / "docs/demo.md", "working walkthrough"),
            file_evidence(ROOT / "docs/requirements-traceability.csv", "traceability table"),
        ],
    }
    reasons = {
        "W3.rvv": "No full-model execution on a compatible RVV 1.0 target.",
        "W5.mechanism": "QEMU returned identical ordered and unordered results on 20,000 deterministic trials; the bounded negative result is reported but earns no attribution credit.",
        "W5.model": "Model-level instruction attribution requires full-model RVV execution, which is unavailable.",
        "W7.independent": "No second conformant implementation or board is available.",
        "W8.cost": "Host-only timing is recorded, but it is not RVV evidence and does not support a defensible cost conclusion.",
        "W9.study": "Final report written; external reproduction and independent review are unavailable.",
    }
    blocked = {"W3.rvv", "W5.model", "W7.independent", "W8.cost"}
    items = []
    for key, weight in WEIGHTS.items():
        if key in mapping:
            items.append({"id": key, "weight": weight, "status": "accepted", "evidence": mapping[key]})
        else:
            items.append(
                {
                    "id": key,
                    "weight": weight,
                    "status": "blocked" if key in blocked else "deferred",
                    "reason": reasons[key],
                }
            )
    ledger = {
        "schema_version": 1,
        "frozen_at": now(),
        "rubric": "plan.md section 2 and docs/adr/0002-completion-scope.md",
        "items": items,
    }
    atomic_json(args.output, ledger)
    result = check_progress(args.output)
    summary = {
        "recorded_at": now(),
        "progress": result,
        "validation": receipt,
        "runs": {
            name: {
                "bundle_sha256": file_digest(ROOT / "runs" / name / "bundle.json"),
                "verdict": load_document(ROOT / "runs" / name / "verdict.json"),
            }
            for name in ("smoke-v1", "self-check", "native-comparison", "contractfast-exploratory", "contractfast-holdout", "selective-exploratory")
        },
        "canary": load_document(ROOT / "runs/canary-study/study.json"),
        "legal_envelope": load_document(ROOT / "runs/legal-envelope/envelope.json")["summary"],
        "hardening": load_document(ROOT / "runs/hardening-evidence/manifest.json"),
    }
    atomic_json(EVIDENCE / "summary.json", summary)
    print(json.dumps({"accepted_points": result["accepted_points"], "items": result["accepted_items"]}, indent=2))


if __name__ == "__main__":
    main()
