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


@pytest.mark.model
def test_canary_holdout_study():
    root = Path("runs/canary-study")
    if not (root / "study.json").exists():
        pytest.skip("canary study evidence unavailable")
    study = load_document(root / "study.json")
    assert study["total_cases"] == 48
    assert study["exploratory"]["cases"] == 32
    assert study["holdout"]["cases"] == 16
    assert study["exploratory"]["failures_sequence"] == 9
    assert study["holdout"]["failures_sequence"] == 5
    selection = study["selection"]["sequence_failure"]
    assert selection["rule"]["threshold"] == 0.10355377197265625
    assert selection["rule"]["selected"] == 17
    result = selection["holdout"]
    assert result["selected"] == 10
    assert result["caught"] == 5
    assert result["recall"] == 1.0
    assert result["precision"] == 0.5
    assert result["cost_ratio_full"] == 10 / 48
    assert result["false_positives"] == 5
    assert result["recall_interval"]["low"] < 1.0
    assert file_digest(Path("prereg/pilot-v1-amendment.md")) == study["provenance"]["prereg_sha256"]
    assert file_digest(Path("corpora/pilot-v1.manifest.json")) == study["provenance"]["corpus_manifest_sha256"]
    assert file_digest(Path("runs/contractfast-holdout/bundle.json")) == study["provenance"]["holdout_bundle_sha256"]


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
