"""Metrics only compare explicitly aligned token histories."""

import numpy as np
from ..errors import VFGError, InsufficientEvidence


def numeric_errors(a, b, epsilon=1e-12):
    a = np.asarray(a, dtype="<f4")
    b = np.asarray(b, dtype="<f4")
    if a.shape != b.shape or a.size == 0:
        raise VFGError("incompatible or empty arrays")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise InsufficientEvidence("non-finite values require an explicit unsupported special-value policy")
    delta = np.abs(b.astype(np.float64) - a.astype(np.float64))

    def ordered(x):
        u = x.view("<u4").astype(np.int64)
        return np.where(u & 0x80000000, 0x80000000 - (u & 0x7FFFFFFF), 0x80000000 + u)

    return {
        "max_absolute_error": float(delta.max()),
        "max_relative_error": float((delta / np.maximum(np.abs(a.astype(np.float64)), epsilon)).max()),
        "max_ulp_error": int(np.abs(ordered(a) - ordered(b)).max()),
        "bit_equal_rate": float(np.mean(a.view("<u4") == b.view("<u4"))),
    }


def sequence_difference(a, b):
    x, y = a["selected_tokens"], b["selected_tokens"]
    for i, (u, v) in enumerate(zip(x, y)):
        if u != v:
            return i
    if len(x) != len(y) or a["stop_reason"] != b["stop_reason"]:
        return min(len(x), len(y))
    return None


def aligned_rows(a, b, alignment):
    if len(a["steps"]) != len(a["selected_tokens"]) or len(b["steps"]) != len(b["selected_tokens"]):
        raise VFGError("step/token counts disagree")
    rows = []
    for i, (left, right) in enumerate(zip(a["steps"], b["steps"])):
        if left["step"] != i or right["step"] != i:
            raise VFGError("missing or reordered output step")
        if left["history_sha256"] != right["history_sha256"]:
            if alignment == "teacher_forced_baseline":
                raise InsufficientEvidence("teacher-forced histories differ")
            break
        rows.append(i)
        if alignment == "free_run" and left["selected_token"] != right["selected_token"]:
            break
    if alignment == "teacher_forced_baseline" and len(a["steps"]) != len(b["steps"]):
        raise InsufficientEvidence("teacher-forced output length differs")
    return rows


def _topk(values, k):
    if k > len(values):
        raise VFGError("top-k exceeds vocabulary")
    return set(np.lexsort((np.arange(len(values)), -values.astype(np.float64)))[:k].tolist())


def compare_rule(rule, pairs):
    numerator = 0.0
    denominator = 0
    maximum = 0.0
    first_divergences = []
    metric = rule.metric
    for a, b, x, y in pairs:
        if x.shape != (len(a["steps"]), a["model"]["vocab_size"]) or y.shape != (
            len(b["steps"]),
            b["model"]["vocab_size"],
        ):
            raise VFGError("result metadata does not match arrays")
        if x.shape[1] != y.shape[1]:
            raise VFGError("vocabulary mismatch")
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise InsufficientEvidence("non-finite logits")
        if (
            a["selected_tokens"] != np.argmax(x, axis=1).tolist()
            or b["selected_tokens"] != np.argmax(y, axis=1).tolist()
        ):
            raise VFGError("recorded greedy choice disagrees with logits")
        divergence = sequence_difference(a, b)
        first_divergences.append(
            {
                "case_id": a["case_id"],
                "position": divergence,
                "censored": divergence is None,
                "observed_steps": len(a["steps"]),
            }
        )
        if metric == "sequence_exact_match_rate":
            numerator += divergence is None
            denominator += 1
            continue
        indices = aligned_rows(a, b, rule.alignment)
        if not indices:
            continue
        if metric in {"max_absolute_error", "max_relative_error", "max_ulp_error", "bit_equal_rate"}:
            result = numeric_errors(x[indices], y[indices], rule.epsilon)
            if metric == "bit_equal_rate":
                numerator += np.count_nonzero(x[indices].view("<u4") == y[indices].view("<u4"))
                denominator += x[indices].size
            else:
                maximum = max(maximum, result[metric])
                denominator += x[indices].size
        elif metric == "argmax_agreement_rate":
            numerator += sum(a["selected_tokens"][i] == b["selected_tokens"][i] for i in indices)
            denominator += len(indices)
        elif metric == "topk_jaccard":
            for i in indices:
                left, right = _topk(x[i], rule.k), _topk(y[i], rule.k)
                numerator += len(left & right) / len(left | right)
                denominator += 1
    if not denominator:
        raise InsufficientEvidence(f"no eligible observations for {rule.id}")
    value = maximum if metric.startswith("max_") else float(numerator / denominator)
    passed = value >= rule.threshold if rule.operator == "ge" else value <= rule.threshold
    return {
        "id": rule.id,
        "metric": metric,
        "alignment": rule.alignment,
        "value": value,
        "operator": rule.operator,
        "threshold": rule.threshold,
        "passed": bool(passed),
        "numerator": None if metric.startswith("max_") else float(numerator),
        "denominator": int(denominator),
        "first_divergences": first_divergences,
    }
