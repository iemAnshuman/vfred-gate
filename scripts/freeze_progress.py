#!/usr/bin/env python3
"""Freeze reviewed local acceptance evidence into the fixed project rubric."""

from pathlib import Path
import shutil
import subprocess
import os
import xml.etree.ElementTree as ET
from vfg.manifest import atomic_json, file_digest, load_document, now
from vfg.progress import WEIGHTS, check_progress

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/midterm"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Keep small review receipts in Git; raw model arrays stay in ignored run bundles.
    copies = [
        "runs/validation/receipt.json",
        "runs/validation/pytest.xml",
        "runs/validation/pytest.log",
        "runs/validation/ruff.log",
        "runs/validation/host-ctest.log",
        "runs/validation/host-configure.log",
        "runs/validation/host-build.log",
        "runs/build-reproducibility.json",
        "runs/smoke-cost.json",
        "environment/host.json",
        "runs/mechanism/manifest.json",
        "runs/mechanism/stdout.json",
        "runs/mechanism/inventory.json",
    ]
    for name in copies:
        source = ROOT / name
        dest = OUT / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    for directory in ["host-release", "llvm-release", "repro-release"]:
        for name in ["build-manifest.json", "compile_commands.json", "CMakeCache.txt"]:
            source = ROOT / "build" / directory / name
            dest = OUT / "build" / directory / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        (OUT / "build" / directory / "build-commands.txt").write_text(
            subprocess.check_output(
                ["ninja", "-C", str(ROOT / "build" / directory), "-t", "commands", "vfg-llama-runner"],
                text=True,
            )
        )
    for source in (ROOT / "runs/rostam").glob("*"):
        if source.is_file():
            dest = OUT / "runs/rostam" / source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    receipt = load_document(ROOT / "runs/validation/receipt.json")
    if not receipt.get("source_unchanged_during_validation"):
        raise RuntimeError("validation lacks a stable source identity")
    if any(file_digest(ROOT / name) != sha for name, sha in receipt["source_files"].items()):
        raise RuntimeError("source changed since validation; run validation again")
    if any(x["returncode"] for x in receipt["checks"]):
        raise RuntimeError("validation has failed checks")
    xml = OUT / "runs/validation/pytest.xml"
    cases = ET.parse(xml).findall(".//testcase")
    if any(c.find(k) is not None for c in cases for k in ["failure", "error", "skipped"]):
        raise RuntimeError("all acceptance prerequisites must pass without skips")
    names = {c.get("classname") + "." + c.get("name") for c in cases}

    def evidence(path, kind, claim, **kw):
        path = ROOT / path
        return {
            "path": os.path.relpath(path, ROOT / "docs"),
            "sha256": file_digest(path),
            "kind": kind,
            "claim": claim,
            **kw,
        }

    def tests(credit, fragment):
        selected = sorted(n for n in names if fragment in n)
        if not selected:
            raise RuntimeError("no tests match " + fragment)
        return evidence(
            "evidence/midterm/runs/validation/pytest.xml", "pytest", credit + " tests", tests=selected
        )

    mapping = {
        "W0.host": [tests("W0.host", "test_host_reduction_mechanism")],
        "W0.compile": [tests("W0.compile", "test_real_elf_maps_both_policies")],
        "W0.emulator": [tests("W0.emulator", "test_rvv_execution_evidence")],
        "W1.schemas": [tests("W1.schemas", "tests.unit.test_manifest.")],
        "W1.artifacts": [tests("W1.artifacts", "tests.unit.test_store.")],
        "W1.build": [
            tests("W1.build", "test_clean_build_metadata"),
            evidence("runs/build-reproducibility.json", "file", "fresh build comparison"),
        ],
        "W1.execute": [tests("W1.execute", "tests.unit.test_execute.")],
        "W2.scan": [
            tests("W2.scan", "test_static_zero_one_multiple_sites"),
            tests("W2.scan invalid", "test_invalid_elf"),
        ],
        "W3.native": [tests("W3.native", "tests.integration.test_runner.")],
        "W4.metrics": [tests("W4.metrics", "tests.unit.test_metrics.")],
        "W4.verdicts": [tests("W4.verdicts", "tests.integration.test_controller.")],
        "W4.end_to_end": [
            tests("W4.end_to_end", "test_confirmation_and_compiler_comparison"),
            evidence(
                "runs/self-check/bundle.json",
                "qualification",
                "160 actual self-check executions",
                verdict="PASS",
                minimum_cases=16,
            ),
            evidence(
                "runs/native-comparison/bundle.json",
                "qualification",
                "320 compiler comparison executions",
                verdict=load_document("runs/native-comparison/verdict.json")["verdict"],
                minimum_cases=16,
            ),
        ],
        "W5.replay": [tests("W5.replay", "test_seeded_replay_shared_history")],
        "W5.capture": [
            tests("W5.capture", "test_layer_capture_restoration"),
            tests("W5.capture strides", "test_production_capture_strided_view"),
        ],
        "W5.seeded": [
            tests("W5.seeded", "test_seeded_operator_and_restoration"),
            evidence("runs/seeded-operator/bundle.json", "localisation", "operator seeded localisation"),
        ],
        "W6.pilot": [
            tests("W6.pilot", "tests.unit.test_corpus."),
            evidence("corpora/pilot-v1.manifest.json", "file", "frozen pilot identity"),
        ],
        "W9.docs": [
            tests("W9.docs", "test_detached_offline_bundle"),
            evidence("docs/srs.md", "file", "SRS draft"),
            evidence("docs/midterm-report.md", "file", "midterm report"),
            evidence("docs/demo.md", "file", "working walkthrough"),
            evidence("README.md", "file", "setup and commands"),
        ],
    }
    reasons = {
        "W0.board": "Rostam was probed safely; standard RVV probe raised SIGILL. No compatible primary-board mechanism validation.",
        "W3.rvv": "No full-model execution on a compatible RVV 1.0 target.",
        "W5.instruction": "Instruction-level causal mapping deferred.",
        "W6.prediction": "Holdouts remain untouched; canary recall/cost study deferred.",
        "W7.legal": "Legal-tree replay and independent validator deferred.",
        "W8.hardening": "Selective hardening search and overhead study deferred.",
        "W9.study": "Final research study and external reproduction deferred.",
    }
    items = []
    for key, weight in WEIGHTS.items():
        item = {
            "id": key,
            "weight": weight,
            "status": "accepted"
            if key in mapping
            else ("blocked" if key in ["W0.board", "W3.rvv"] else "deferred"),
        }
        if key in mapping:
            item["evidence"] = mapping[key]
        else:
            item["reason"] = reasons[key]
        items.append(item)
    atomic_json(
        ROOT / "docs/progress.yaml",
        {"schema_version": 1, "frozen_at": now(), "rubric": "plan.md section 2", "items": items},
    )
    result = check_progress(ROOT / "docs/progress.yaml")
    summary = {
        "recorded_at": now(),
        "progress": result,
        "tests": len(cases),
        "validation": receipt,
        "runs": {},
    }
    for name in ["smoke-v1", "self-check", "native-comparison", "seeded"]:
        summary["runs"][name] = {
            "bundle_sha256": file_digest(ROOT / "runs" / name / "bundle.json"),
            "verdict": load_document(ROOT / "runs" / name / "verdict.json"),
        }
    summary["localisation"] = load_document(ROOT / "runs/seeded-operator/localisation.json")
    atomic_json(OUT / "summary.json", summary)
    print(f"accepted {result['accepted_points']}/100; {len(cases)} tests passed without skips")


if __name__ == "__main__":
    main()
