from pathlib import Path
import shutil
import os
import subprocess
import pytest
from vfg.manifest import load_document, file_digest
from vfg.controller import rederive
from vfg.replay.localise import verify_localisation


@pytest.mark.rvv
def test_rvv_execution_evidence():
    root = Path("runs/mechanism")
    if not (root / "manifest.json").exists():
        pytest.skip("RVV probe not run")
    manifest = load_document(root / "manifest.json")
    data = load_document(root / "stdout.json")
    assert manifest["execution_class"] == "emulator"
    assert manifest["binary_sha256"] == file_digest(root / "probe.elf")
    assert len(data["records"]) == 140 and manifest["distinct_cases"] == 28
    assert data["ordered_matches_scalar"] and data["frm"] == 0
    groups = {}
    for row in data["records"]:
        assert row["ordered_bits"] == row["scalar_bits"]
        assert len(row["input_bits"]) == row["n"]
        groups.setdefault((row["fixture"], row["n"]), []).append(row)
    assert all(
        len(rows) == 5 and len({(r["ordered_bits"], r["unordered_bits"]) for r in rows}) == 1
        for rows in groups.values()
    )
    assert {r["n"] for r in data["records"]} == {0, 1, 4, 7, 8, 9, 19}


def test_host_reduction_mechanism():
    binary = Path("build/host-debug/microbench/vfg-microbench")
    if not binary.exists():
        pytest.skip("host microbench not built")
    p = subprocess.run([str(binary), "--self-test"], capture_output=True, text=True)
    assert p.returncode == 0 and "reduction references passed" in p.stdout


@pytest.mark.model
def test_confirmation_and_compiler_comparison():
    for name, modecount in [("self-check", 1), ("native-comparison", 2)]:
        root = Path("runs") / name
        if not (root / "bundle.json").exists():
            pytest.skip(f"{name} not complete")
        result = rederive(root)["verdict"]
        assert result["verdict"] in ("PASS", "FAIL")
        if name == "self-check":
            assert result["verdict"] == "PASS"
        assert result["evidence"]["distinct_cases"] == 16
        assert result["evidence"]["completed_jobs"] == 160 * modecount
        assert all(x["stable"] for x in result["evidence"]["stability"])
        inputs = load_document(root / "inputs.json")
        assert all(c["split"] == "exploratory" for c in inputs["selected_cases"])
        if name == "native-comparison":
            assert inputs["baseline"]["compiler"]["sha256"] != inputs["candidate"]["compiler"]["sha256"]
            assert not result["evidence"]["manifest_diff"]["uncontrolled"]


@pytest.mark.model
def test_detached_offline_bundle(tmp_path):
    root = Path("runs/smoke-v1")
    if not (root / "bundle.json").exists():
        pytest.skip("smoke bundle unavailable")
    detached = tmp_path / "detached"
    shutil.copytree(root, detached, copy_function=os.link)
    assert rederive(detached)["verdict"]["verdict"] == "PASS"
    from vfg.report import render_report

    first = rederive(detached)
    render_report(detached, detached / "report")
    render_report(detached, detached / "report")
    assert rederive(detached) == first


@pytest.mark.model
def test_seeded_replay_shared_history():
    root = Path("runs/seeded-operator")
    if not (root / "bundle.json").exists():
        pytest.skip("localisation unavailable")
    result = verify_localisation(root)
    assert result["history_matched"] and result["original_discrepancy_preserved"]
    assert result["first_free_run_token_difference"] == 0


@pytest.mark.model
def test_layer_capture_restoration():
    root = Path("runs/seeded-operator/layer-discovery")
    if not (root / "bundle.json").exists():
        pytest.skip("layer localisation unavailable")
    result = verify_localisation(root)
    assert result["baseline_restored"]
    assert result["earliest_difference"]["name"] == "l_out-0"
    assert sum(name.startswith("l_out-") for name in result["layer_map"]) == 32


@pytest.mark.model
def test_clean_build_metadata():
    path = Path("runs/build-reproducibility.json")
    if not path.exists():
        pytest.skip("clean build comparison unavailable")
    result = load_document(path)
    assert file_digest(result["left"]) == result["left_sha256"]
    assert file_digest(result["right"]) == result["right_sha256"]
    assert result["section_sets_match"] and all(s["equal"] for s in result["sections"].values())
    assert result["debug_object_symbols"]["left"] != result["debug_object_symbols"]["right"]
    for directory in ["build/llvm-release", "build/repro-release"]:
        manifest = load_document(Path(directory) / "build-manifest.json")
        assert manifest["verified_upstream_files"] > 100
        assert file_digest(Path(directory) / "compile_commands.json") == manifest["compile_commands_sha256"]
        assert file_digest(Path(directory) / "CMakeCache.txt") == manifest["cmake_cache_sha256"]
        assert file_digest(Path(directory) / "runner/vfg-llama-runner") == manifest["binary_sha256"]
