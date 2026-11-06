"""Sensitivity-ranked canary selection and held-out evaluation."""

from pathlib import Path
import math

import numpy as np

from ..compare.metrics import aligned_rows, sequence_difference
from ..manifest import atomic_json, load_document, now
from ..store import read_array


def wilson(successes, total, z=1.959963984540054):
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return {"low": max(0.0, centre - margin), "high": min(1.0, centre + margin)}


def per_case_metrics(root):
    from ..controller import rederive

    root = Path(root)
    rederive(root)
    inputs = load_document(root / "inputs.json")
    run = load_document(root / "run.json")
    cases = []
    for case in inputs["selected_cases"]:
        jobs = {
            role: next(
                job
                for job in run["jobs"]
                if job["case_id"] == case["id"]
                and job["role"] == role
                and job["mode"] == "free_run"
                and job["repetition"] == 0
            )
            for role in ("baseline", "candidate")
        }
        results = {}
        arrays = {}
        for role, job in jobs.items():
            output = root / job["path"] / "output"
            results[role] = load_document(output / "result.json")
            arrays[role] = read_array(output, results[role])
        a, b = results["baseline"], results["candidate"]
        x, y = arrays["baseline"], arrays["candidate"]
        rows = aligned_rows(a, b, "free_run")
        divergence = sequence_difference(a, b)
        if rows:
            equal = np.count_nonzero(x[rows].view("<u4") == y[rows].view("<u4"))
            total = x[rows].size
            bit_rate = float(equal / total)
            argmax = sum(a["selected_tokens"][i] == b["selected_tokens"][i] for i in rows) / len(rows)
        else:
            bit_rate = 0.0 if divergence is not None else 1.0
            argmax = 0.0 if divergence is not None else 1.0
        values = np.partition(
            np.asarray(x, dtype=np.float64), -2, axis=1
        )[:, -2:]
        margins = values.max(axis=1) - values.min(axis=1)
        cases.append(
            {
                "case_id": case["id"],
                "category": case["category"],
                "minimum_margin": float(margins.min()),
                "mean_margin": float(margins.mean()),
                "steps": int(len(x)),
                "aligned_steps": len(rows),
                "bit_equal_rate": bit_rate,
                "argmax_agreement_rate": float(argmax),
                "first_divergence": divergence,
                "sequence_failure": divergence is not None,
                "bit_failure": bit_rate < 1.0,
            }
        )
    return cases


def rank_cases(rows, failure_key="sequence_failure"):
    return sorted(rows, key=lambda row: (row["minimum_margin"], row["case_id"]))


def select_threshold(exploratory, failure_key="sequence_failure"):
    """Smallest margin threshold that covers every observed exploratory failure."""
    ranked = rank_cases(exploratory, failure_key)
    failures = [row for row in ranked if row[failure_key]]
    if not failures:
        return {
            "failure_key": failure_key,
            "threshold": None,
            "selected": 0,
            "failures": 0,
            "reason": "no exploratory failure observed; recall is undefined",
        }
    selected = []
    covered = 0
    for row in ranked:
        selected.append(row)
        covered += row[failure_key]
        if covered == len(failures):
            break
    threshold = max(row["minimum_margin"] for row in selected)
    return {
        "failure_key": failure_key,
        "threshold": threshold,
        "selected": len(selected),
        "failures": len(failures),
        "selected_ids": [row["case_id"] for row in selected],
    }


def evaluate(holdout, threshold, exploratory_selected, failure_key="sequence_failure"):
    if threshold is None:
        return {
            "failure_key": failure_key,
            "threshold": None,
            "selected": 0,
            "failures": len([row for row in holdout if row[failure_key]]),
            "recall": None,
            "cost_ratio": None,
        }
    selected = [row for row in holdout if row["minimum_margin"] <= threshold]
    failures = [row for row in holdout if row[failure_key]]
    caught = [row for row in selected if row[failure_key]]
    by_count = sorted(holdout, key=lambda row: (row["minimum_margin"], row["case_id"]))[
        : min(exploratory_selected, len(holdout))
    ]
    caught_by_count = [row for row in by_count if row[failure_key]]
    return {
        "failure_key": failure_key,
        "threshold": threshold,
        "selected": len(selected),
        "selected_ids": [row["case_id"] for row in selected],
        "failures": len(failures),
        "failure_ids": [row["case_id"] for row in failures],
        "caught": len(caught),
        "caught_ids": [row["case_id"] for row in caught],
        "recall": len(caught) / len(failures) if failures else None,
        "recall_interval": wilson(len(caught), len(failures)) if failures else None,
        "false_positives": len(selected) - len(caught),
        "cost_ratio": len(selected) / len(holdout),
        "fixed_count": {
            "selected": len(by_count),
            "caught": len(caught_by_count),
            "recall": len(caught_by_count) / len(failures) if failures else None,
            "cost_ratio": len(by_count) / len(holdout),
        },
    }


def run_study(exploratory_root, holdout_root, output):
    exploratory = per_case_metrics(exploratory_root)
    holdout = per_case_metrics(holdout_root)
    result = {
        "schema_version": 1,
        "generated_at": now(),
        "exploratory": {
            "cases": len(exploratory),
            "failures_sequence": sum(row["sequence_failure"] for row in exploratory),
            "failures_bits": sum(row["bit_failure"] for row in exploratory),
        },
        "holdout": {
            "cases": len(holdout),
            "failures_sequence": sum(row["sequence_failure"] for row in holdout),
            "failures_bits": sum(row["bit_failure"] for row in holdout),
        },
        "selection": {},
        "rows": {"exploratory": exploratory, "holdout": holdout},
    }
    for key in ("sequence_failure", "bit_failure"):
        selection = select_threshold(exploratory, key)
        result["selection"][key] = {
            "rule": selection,
            "holdout": evaluate(holdout, selection["threshold"], selection["selected"], key),
        }
    if output:
        atomic_json(output, result)
    return result
