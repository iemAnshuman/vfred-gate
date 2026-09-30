import pytest
from vfg.progress import check_progress, WEIGHTS
from vfg.manifest import atomic_json, file_digest
from vfg.errors import VFGError


def ledger():
    return {
        "items": [
            {"id": k, "weight": v, "status": "deferred", "reason": "not validated"}
            for k, v in WEIGHTS.items()
        ]
    }


def test_unearned_points_are_not_completion(tmp_path):
    p = tmp_path / "ledger.json"
    atomic_json(p, ledger())
    assert check_progress(p)["accepted_points"] == 0


def test_duplicate_and_changed_weights_rejected(tmp_path):
    p = tmp_path / "ledger.json"
    x = ledger()
    x["items"].append(x["items"][0])
    atomic_json(p, x)
    with pytest.raises(VFGError, match="duplicate"):
        check_progress(p)
    x = ledger()
    x["items"][0]["weight"] += 1
    atomic_json(p, x)
    with pytest.raises(VFGError, match="weights"):
        check_progress(p)


def test_skipped_prerequisite_earns_nothing(tmp_path):
    xml = tmp_path / "tests.xml"
    xml.write_text(
        '<testsuites><testsuite><testcase classname="target" name="check"><skipped/></testcase></testsuite></testsuites>'
    )
    x = ledger()
    x["items"][0].update(
        status="accepted",
        evidence=[
            {
                "path": str(xml),
                "sha256": file_digest(xml),
                "kind": "pytest",
                "claim": "hardware",
                "tests": ["target.check"],
            }
        ],
    )
    p = tmp_path / "ledger.json"
    atomic_json(p, x)
    with pytest.raises(VFGError, match="failed or skipped"):
        check_progress(p)


def test_corrupt_acceptance_artifact_rejected(tmp_path):
    artifact = tmp_path / "evidence"
    artifact.write_text("changed")
    x = ledger()
    x["items"][0].update(
        status="accepted",
        evidence=[{"path": str(artifact), "sha256": "0" * 64, "kind": "file", "claim": "claim"}],
    )
    p = tmp_path / "ledger.json"
    atomic_json(p, x)
    with pytest.raises(VFGError, match="changed"):
        check_progress(p)
