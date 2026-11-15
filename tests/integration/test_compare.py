from pathlib import Path
import shutil

import pytest

from vfg.controller import rederive
from vfg.workflow import compare

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models/smollm2-360m-instruct-q8_0.gguf"


@pytest.mark.model
def test_self_comparison_passes_and_rederives(tmp_path):
    if not MODEL.is_file() or not shutil.which("cmake") or not shutil.which("ninja"):
        pytest.skip("pinned model or native build tools unavailable")
    summary = compare(MODEL, output=tmp_path / "run", cases=2, repetitions=2, max_tokens=8, progress=lambda m: None)
    assert summary["verdict"] == "PASS" and summary["exit_code"] == 0
    assert summary["explain"] is None
    assert Path(summary["report"]).is_file()
    assert rederive(tmp_path / "run/qualification")["bundle_sha256"] == summary["bundle_sha256"]


@pytest.mark.model
def test_record_then_check_passes(tmp_path):
    if not MODEL.is_file() or not shutil.which("cmake"):
        pytest.skip("pinned model or native build tools unavailable")
    from vfg.reference import check, record

    quiet = lambda m: None  # noqa: E731
    record(MODEL, output=tmp_path / "ref", cases=2, repetitions=2, max_tokens=8, progress=quiet)
    result = check(tmp_path / "ref", MODEL, output=tmp_path / "chk", progress=quiet)
    assert result["verdict"] == "PASS"
    assert rederive(tmp_path / "chk")["verdict"]["verdict"] == "PASS"
    other = tmp_path / "other.gguf"
    other.write_bytes(b"GGUF" + b"\0" * 8)
    with pytest.raises(Exception, match="model differs"):
        check(tmp_path / "ref", other, output=tmp_path / "chk2", progress=quiet)
