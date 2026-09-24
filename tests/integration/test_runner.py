import json
from pathlib import Path
import subprocess
import pytest
import numpy as np
from vfg.manifest import file_digest

BINARY = Path("build/host-release/runner/vfg-llama-runner")
LOCK = Path("models/model.lock.json")


@pytest.fixture
def runner_request(tmp_path):
    if not BINARY.exists():
        pytest.skip("runner not built")
    model = json.loads(LOCK.read_text())
    path = LOCK.parent / model["filename"]
    if not path.exists():
        pytest.skip("pinned model unavailable")
    return {
        "schema_version": 1,
        "model_path": str(path.resolve()),
        "model_sha256": model["sha256"],
        "case_id": "runner-test",
        "mode": "free_run",
        "prompt_tokens": [1, 4093, 198, 1780, 314, 827, 8055, 827, 47, 2, 198, 1, 520, 9531, 198],
        "max_tokens": 8,
        "context": 512,
    }


def call(tmp_path, runner_request, name):
    p = tmp_path / (name + ".json")
    p.write_text(json.dumps(runner_request))
    out = tmp_path / name
    r = subprocess.run([str(BINARY.resolve()), str(p), str(out)], capture_output=True, text=True, timeout=60)
    return r, out


@pytest.mark.model
def test_real_model_repetitions_and_argmax(tmp_path, runner_request):
    results = []
    for i in range(5):
        proc, out = call(tmp_path, runner_request, str(i))
        assert proc.returncode == 0, proc.stderr[-1000:]
        data = json.loads((out / "result.json").read_text())
        a = np.fromfile(out / "logits.f32", dtype="<f4").reshape(data["logits_shape"])
        assert data["selected_tokens"] == np.argmax(a, axis=1).tolist()
        assert data["logits_sha256"] == file_digest(out / "logits.f32")
        assert data["stop_reason"] == "eos"
        results.append(data)
    assert len({r["logits_sha256"] for r in results}) == 1
    assert all(r["selected_tokens"] == results[0]["selected_tokens"] for r in results)


@pytest.mark.model
@pytest.mark.parametrize(
    "change",
    [
        {"prompt_tokens": [-1]},
        {"prompt_tokens": [2**40]},
        {"context": 8},
        {"max_tokens": 0},
        {"mode": "unknown"},
        {"unexpected": "value"},
        {"model_sha256": "0" * 64},
    ],
)
def test_invalid_request_fails_closed(tmp_path, runner_request, change):
    proc, out = call(tmp_path, runner_request | change, "invalid")
    assert proc.returncode == 4
    assert not (out / "result.json").exists()


@pytest.mark.model
def test_capture_does_not_change_tested_output(tmp_path, runner_request):
    a, adir = call(tmp_path, runner_request, "plain")
    b, bdir = call(tmp_path, runner_request | {"capture": {"mode": "layer"}}, "capture")
    assert a.returncode == b.returncode == 0
    assert (adir / "logits.f32").read_bytes() == (bdir / "logits.f32").read_bytes()
    assert (bdir / "captures.jsonl").stat().st_size > 0


@pytest.mark.model
def test_tokenize_and_context_budget(tmp_path, runner_request):
    q = {k: runner_request[k] for k in ("schema_version", "model_path", "model_sha256")}
    q.update(mode="tokenize", texts=[{"id": "x", "text": "What is two plus two?"}])
    proc, out = call(tmp_path, q, "tokens")
    assert proc.returncode == 0, proc.stderr[-1000:]
    item = json.loads((out / "result.json").read_text())["cases"][0]
    assert item["tokens"] == runner_request["prompt_tokens"]
    assert "What is two plus two?" in item["formatted_text"]
