import pytest

from vfg.harden.ddmin import ddmin


def test_ddmin_finds_a_single_required_site():
    sites = ["a", "b", "c"]
    minimal, trace = ddmin(sites, lambda subset: "b" in subset)
    assert minimal == ["b"]
    assert trace[0]["passed"] is True
    assert any(not row["passed"] for row in trace)


def test_ddmin_finds_a_pair():
    sites = ["a", "b", "c", "d"]
    minimal, _ = ddmin(sites, lambda subset: {"b", "d"} <= set(subset))
    assert set(minimal) == {"b", "d"}


def test_ddmin_rejects_a_failing_full_set():
    with pytest.raises(RuntimeError, match="full hardening set"):
        ddmin(["a", "b"], lambda subset: False)


def test_ddmin_is_empty_for_empty_input():
    assert ddmin([], lambda subset: True) == ([], [])
