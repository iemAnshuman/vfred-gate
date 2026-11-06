from pathlib import Path

import pytest

from vfg.manifest import file_digest, load_document


@pytest.mark.rvv
def test_legal_envelope_evidence():
    root = Path("runs/legal-envelope")
    if not (root / "manifest.json").exists():
        pytest.skip("legal envelope evidence unavailable")
    manifest = load_document(root / "manifest.json")
    envelope = load_document(root / "envelope.json")
    assert file_digest(root / "envelope.json") == manifest["outputs"]["envelope.json"]
    assert file_digest(Path("runs/mechanism/stdout.json")) == envelope["source_records_sha256"]
    summary = envelope["summary"]
    assert summary["ordered_matches_scalar"]
    assert summary["all_observed_contained"]
    assert summary["independent_equal"]
    assert summary["independent_records"] >= 16
    assert summary["random_samples"] == 24
    assert summary["random_samples_with_multiple_results"] >= 20
    assert summary["random_maximum_support_size"] > 1000
    assert all(item["contained"] for item in envelope["random_samples"])
    assert all(not item["equal"] or item["python_size"] == item["cpp_size"] for item in envelope["independent_sampler"])
    for control in envelope["controls"]:
        if "inside" in control:
            assert control["inside"] is False
        else:
            assert control["observed_in_wrong_seed_envelope"] is False


@pytest.mark.rvv
def test_emulator_search_is_a_bounded_negative():
    root = Path("runs/mechanism-search")
    if not (root / "manifest.json").exists():
        pytest.skip("emulator search evidence unavailable")
    manifest = load_document(root / "manifest.json")
    data = load_document(root / "stdout.json")
    assert manifest["found"] is False
    assert manifest["search"]["trials"] == 20000
    assert data["found"] is False
    assert data["dynamic"]["ordered_invocations"] > 0
    assert data["dynamic"]["unordered_invocations"] > 0
    assert "vfredosum.vs" in manifest["static_sites"]
    assert "vfredusum.vs" in manifest["static_sites"]
    assert manifest["physical_board_gate"] == "blocked"
