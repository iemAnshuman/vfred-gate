import json
from pathlib import Path
import shutil
import pytest
from typer.testing import CliRunner
from vfg.cli import app
from vfg.controller import rederive
from vfg.controller.qualification import assess
from vfg.manifest import load_document
from vfg.errors import VFGError

ROOT = Path("runs/smoke-v1")


@pytest.fixture
def evidence():
    if not (ROOT / "bundle.json").exists():
        pytest.skip("real smoke bundle not generated")
    return load_document(ROOT / "inputs.json"), load_document(ROOT / "run.json")["jobs"]


@pytest.mark.model
def test_raw_verdict_reconstruction(evidence):
    assert rederive(ROOT)["verdict"]["verdict"] == "PASS"


@pytest.mark.model
def test_missing_repeat_uncontrolled_and_error(evidence):
    inputs, jobs = evidence
    verdict, _ = assess(ROOT, inputs, jobs[:-1])
    assert verdict.verdict == "INCONCLUSIVE"
    inputs["candidate"]["flags"].append("-unexpected")
    verdict, _ = assess(ROOT, inputs, jobs)
    assert verdict.verdict == "INCONCLUSIVE"
    verdict, _ = assess(ROOT, inputs, jobs + [jobs[0]])
    assert verdict.verdict == "ERROR"


@pytest.mark.model
def test_corrupt_evidence_fails_closed(tmp_path, evidence):
    # Hard links keep this integrity test small; replace, never modify, the linked file.
    shutil.copytree(ROOT, tmp_path / "bundle", copy_function=__import__("os").link)
    p = tmp_path / "bundle" / evidence[1][0]["path"] / "output/result.json"
    p.unlink()
    p.write_text("{}")
    with pytest.raises(VFGError, match="hash mismatch"):
        rederive(tmp_path / "bundle")


@pytest.mark.model
def test_unindexed_evidence_rejected(tmp_path, evidence):
    shutil.copytree(ROOT, tmp_path / "bundle", copy_function=__import__("os").link)
    (tmp_path / "bundle" / "extra.txt").write_text("unverified")
    with pytest.raises(VFGError, match="unindexed"):
        rederive(tmp_path / "bundle")


@pytest.mark.model
def test_report_escapes_html(tmp_path, evidence):
    from jinja2 import Environment, select_autoescape

    template = Environment(autoescape=select_autoescape(default=True)).from_string("{{ x }}")
    assert "<script>" not in template.render(x="<script>alert(1)</script>")
    from vfg.report import render_report

    path = render_report(ROOT, tmp_path / "report")
    assert "none observed (censored)" in path.read_text()
    assert "http://" not in path.read_text() and "https://" not in path.read_text()


def test_cli_invalid_contract_is_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"unknown":true}')
    result = CliRunner().invoke(app, ["qualify", "--plan", str(p), "--output", str(tmp_path / "run")])
    assert result.exit_code == 4
    assert json.loads((tmp_path / "run/verdict.json").read_text())["verdict"] == "ERROR"


@pytest.mark.model
def test_cli_exit_codes(evidence, tmp_path):
    runner = CliRunner()
    assert runner.invoke(app, ["verify", "--run", str(ROOT)]).exit_code == 0
    assert runner.invoke(app, ["validate", "--plan", "plans/smoke.json"]).exit_code == 0
