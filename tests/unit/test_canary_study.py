from vfg.canary.study import evaluate, select_threshold, wilson


def rows(margins, failures):
    return [
        {
            "case_id": f"c{index:03d}",
            "minimum_margin": margin,
            "sequence_failure": failure,
            "bit_failure": failure,
        }
        for index, (margin, failure) in enumerate(zip(margins, failures))
    ]


def test_selection_covers_observed_failures_and_freezes_threshold():
    exploratory = rows([0.1, 0.2, 0.3, 0.4], [True, False, False, True])
    selection = select_threshold(exploratory)
    assert selection["threshold"] == 0.4
    assert selection["selected"] == 4
    assert selection["failures"] == 2


def test_no_failure_leaves_recall_undefined():
    selection = select_threshold(rows([0.1, 0.2], [False, False]))
    assert selection["threshold"] is None
    assert "undefined" in selection["reason"]


def test_holdout_recall_cost_and_false_positives():
    exploratory = rows([0.1, 0.2], [True, True])
    selection = select_threshold(exploratory)
    holdout = rows([0.05, 0.15, 0.25, 0.35], [True, False, False, True])
    result = evaluate(holdout, selection["threshold"], selection["selected"], total_cases=8)
    assert result["selected"] == 2
    assert result["failures"] == 2
    assert result["caught"] == 1
    assert result["recall"] == 0.5
    assert result["precision"] == 0.5
    assert result["false_positives"] == 1
    assert result["cost_ratio"] == 0.5
    assert result["cost_ratio_full"] == 0.25
    assert result["fixed_count"]["selected"] == 2


def test_wilson_interval_is_bounded():
    interval = wilson(1, 1)
    assert interval["low"] < 1.0
    assert interval["high"] == 1.0
    assert wilson(0, 0) is None
