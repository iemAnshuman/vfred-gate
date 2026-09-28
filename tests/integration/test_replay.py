from pathlib import Path
import json
import pytest
from vfg.replay.localise import compare_captures, verify_localisation
from vfg.errors import InsufficientEvidence


@pytest.mark.model
def test_seeded_operator_and_restoration():
    root = Path("runs/seeded-operator")
    if not (root / "bundle.json").exists():
        pytest.skip("seeded localisation not generated")
    result = verify_localisation(root)
    assert result["injected_diagnostic"]
    assert result["history_matched"] and result["baseline_restored"]
    assert result["original_discrepancy_preserved"]
    assert result["earliest_difference"]["name"] == "l_out-0"
    assert result["earliest_difference"]["op"] == "ADD"
    assert result["earliest_difference"]["injected"]
    assert result["instruction_site"] is None
    assert result["logit_numeric"]["max_absolute_error"] > 0
    layer = verify_localisation(root / "layer-discovery")
    assert layer["earliest_difference"]["name"] == "l_out-0"
    # Verify the metadata archived from actual model callbacks.
    events = [
        json.loads(x) for x in (root / "baseline-before/output/captures.jsonl").read_text().splitlines()
    ]
    assert all("strides" in event for event in events)


def test_mismatched_capture_histories_fail(tmp_path):
    event = {
        "ordinal": 0,
        "position": 0,
        "prediction_step": 0,
        "history_sha256": "a",
        "name": "tensor",
        "op": "ADD",
        "shape": [1, 1, 1, 1],
        "dtype": "<f4",
        "sha256": "x",
    }
    with pytest.raises(InsufficientEvidence, match="aligned"):
        compare_captures([event], [event | {"history_sha256": "b"}], tmp_path, tmp_path)


@pytest.mark.model
def test_production_capture_strided_view(tmp_path):
    import subprocess

    root = Path.cwd()
    build = root / "build/host-release"
    libs = [
        build / "llama/src/libllama.a",
        build / "llama/ggml/src/libggml.a",
        build / "llama/ggml/src/libggml-cpu.a",
        build / "llama/ggml/src/libggml-base.a",
    ]
    if not all(p.exists() for p in libs):
        pytest.skip("native static libraries unavailable")
    sha = (
        build
        / "runner/CMakeFiles/vfg-llama-runner.dir/__/third_party/llama.cpp/vendor/hash/sha256/sha256.c.o"
    )
    binary = tmp_path / "capture-test"
    command = [
        "c++",
        "-std=c++17",
        "-O1",
        "-Irunner/include",
        "-Ithird_party/llama.cpp/include",
        "-Ithird_party/llama.cpp/ggml/include",
        "-Ithird_party/llama.cpp/vendor",
        "tests/native/capture_test.cpp",
        "runner/src/protocol.cpp",
        str(sha),
        *[str(p) for p in libs],
        "-pthread",
        "-o",
        str(binary),
    ]
    p = subprocess.run(command, capture_output=True, text=True, timeout=90)
    assert p.returncode == 0, p.stderr
    p = subprocess.run([str(binary), str(tmp_path / "out")], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    assert "strided capture excludes padding" in p.stdout
