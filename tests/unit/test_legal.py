import pytest
from vfg.errors import VFGError
from vfg.legal import (
    bits_of,
    chunk_envelope,
    contains,
    seed_root_envelope,
    subtree_support,
    summarize,
    value_of,
)


def test_exact_case_all_trees_agree():
    support = subtree_support([1.0, 2.0, 3.0, 4.0])
    assert support == [10.0]


def test_wider_intermediate_exposes_a_legal_difference():
    values = [16777216.0, 1.0, -16777216.0, 1.0]
    support = subtree_support(values)
    assert 1.0 in support
    assert 2.0 in support
    assert len(support) >= 2


def test_seed_participates_as_a_leaf():
    support = subtree_support([0.0, 16777216.0, 1.0, -16777216.0, 1.0])
    assert 1.0 in support


def test_seed_root_model_is_a_subset():
    values = [16777216.0, 1.0, -16777216.0, 1.0]
    leaves = chunk_envelope(0.0, values, chunk_size=8)
    root = seed_root_envelope(0.0, values, chunk_size=8)
    assert set(root["support"]) <= set(leaves["support"])


def test_chunking_changes_the_permitted_set():
    values = [16777216.0, 1.0, -16777216.0, 1.0, 1.0, 1.0]
    one = chunk_envelope(0.0, values, chunk_size=8)
    two = chunk_envelope(0.0, values, chunk_size=3)
    assert one["chunks"] == 1
    assert two["chunks"] == 2
    assert set(two["support"]) <= set(one["support"])


def test_empty_input_returns_seed_and_executes_nothing():
    result = chunk_envelope(3.25, [])
    assert result["support"] == [3.25]
    assert result["reduction_executions"] == 0


def test_bits_round_trip_and_signed_zero_canonicalises():
    assert value_of(bits_of(-12.5)) == -12.5
    assert bits_of(0.0) == bits_of(-0.0)


def test_containment_and_summary():
    values = [16777216.0, 1.0, -16777216.0, 1.0]
    envelope = chunk_envelope(0.0, values)
    summary = summarize(envelope, bits_of(1.0))
    assert summary["contained"]
    assert summary["support_size"] >= 2
    assert summary["interval"]["minimum"] <= 1.0 <= summary["interval"]["maximum"]
    assert summary["other_legal_examples"]
    assert not contains(envelope, bits_of(12345.0))


def test_support_cap_fails_closed():
    values = [16777216.0, 1.0, -16777216.0, 1.0]
    with pytest.raises(VFGError, match="exceeds"):
        subtree_support(values, cap=1)


def test_non_finite_operands_rejected():
    with pytest.raises(VFGError, match="finite"):
        subtree_support([0.0, float("inf")])


def test_result_is_deterministic():
    values = [3.5, 1e-8, -3.5, 2.0]
    assert chunk_envelope(0.0, values)["support"] == chunk_envelope(0.0, values)["support"]
