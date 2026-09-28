"""Bounded fresh-context teacher forcing and observed tensor localisation."""

import json
from pathlib import Path
import re
import numpy as np
from ..compare.metrics import numeric_errors, sequence_difference
from ..controller.qualification import ResolvedPlan, runner_request, validate_output
from ..controller import rederive
from ..errors import VFGError, InsufficientEvidence
from ..execute import execute_runner
from ..manifest import atomic_json, file_digest, load_document, now
from ..schema import Plan, ModelLock, Contract, Target, Stack, CorpusCase
from ..store import read_array, safe_child, seal_bundle, verify_bundle


def capture_events(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def compare_captures(left, right, left_root, right_root):
    if len(left) != len(right):
        raise InsufficientEvidence("capture event counts differ")
    differences = []
    keys = ("ordinal", "position", "prediction_step", "history_sha256", "name", "op", "shape", "dtype")
    for a, b in zip(left, right):
        if any(a[k] != b[k] for k in keys):
            raise InsufficientEvidence("capture keys/history are not aligned")
        if a["sha256"] != b["sha256"]:
            item = {k: a[k] for k in keys}
            item.update(baseline_sha256=a["sha256"], candidate_sha256=b["sha256"], injected=b["injected"])
            if "payload" in a and "payload" in b:
                item["numeric"] = numeric_errors(
                    np.fromfile(safe_child(left_root, a["payload"]), dtype="<f4"),
                    np.fromfile(safe_child(right_root, b["payload"]), dtype="<f4"),
                )
            differences.append(item)
    return differences


def _resolved(inputs):
    return ResolvedPlan(
        Plan.model_validate(inputs["plan"]),
        ModelLock.model_validate(inputs["model"]),
        Path(inputs["model_path"]),
        Contract.model_validate(inputs["contract"]),
        Target.model_validate(inputs["target"]),
        {r: Stack.model_validate(inputs[r]) for r in ("baseline", "candidate")},
        {r: Path(inputs["binaries"][r]) for r in ("baseline", "candidate")},
        [CorpusCase.model_validate(c) for c in inputs["selected_cases"]],
        inputs,
    )


def localise(qualification, case_id, capture="layer", output=None):
    if capture not in ("layer", "operator"):
        raise VFGError("capture must be layer or operator")
    qualification = Path(qualification).resolve()
    source = rederive(qualification)
    inputs = load_document(qualification / "inputs.json")
    run = load_document(qualification / "run.json")
    resolved = _resolved(inputs)
    if file_digest(resolved.model_path) != resolved.model.sha256:
        raise VFGError("replay model changed")
    for role in ("baseline", "candidate"):
        if file_digest(resolved.binaries[role]) != resolved.stacks[role].binary_sha256:
            raise VFGError("replay binary changed")
    case = next((c for c in resolved.cases if c.id == case_id), None)
    if case is None:
        raise VFGError("unknown qualification case")
    paths = {
        r: qualification
        / next(
            j["path"]
            for j in run["jobs"]
            if j["case_id"] == case_id and j["role"] == r and j["mode"] == "free_run" and j["repetition"] == 0
        )
        / "output"
        for r in ("baseline", "candidate")
    }
    records = {r: load_document(p / "result.json") for r, p in paths.items()}
    a, b = records["baseline"], records["candidate"]
    x, y = read_array(paths["baseline"], a), read_array(paths["candidate"], b)
    divergence = sequence_difference(a, b)
    first_numeric = next(
        (i for i in range(min(len(x), len(y))) if not np.array_equal(x[i].view("<u4"), y[i].view("<u4"))),
        None,
    )
    step = divergence if divergence is not None else first_numeric
    if step is None:
        raise InsufficientEvidence("no output difference observed to localise")
    step = min(step, len(a["selected_tokens"]) - 1)
    forced = a["selected_tokens"][: step + 1]
    output = Path(
        output or qualification.parent / (qualification.name + "-" + case_id + "-" + capture)
    ).resolve()
    if output.exists() and any(output.iterdir()):
        raise VFGError("localisation output is not empty")
    output.mkdir(parents=True, exist_ok=True)
    chosen = {"mode": "layer", "match": "", "payloads": False, "schema_version": 1}
    layer_result = None
    if capture == "operator":
        layer_path = output / "layer-discovery"
        layer_result = localise(qualification, case_id, "layer", layer_path)
        name = layer_result["earliest_difference"]["name"]
        matched = re.search(r"-(\d+)$", name)
        chosen = {
            "schema_version": 1,
            "mode": "operator",
            "match": "-" + matched.group(1) if matched else name,
            "payloads": True,
        }
    started = now()
    results = {}
    events = {}
    requests = {}
    # Fresh contexts before, during, and after the candidate perturbation.
    for label, role in [
        ("baseline-before", "baseline"),
        ("candidate", "candidate"),
        ("baseline-after", "baseline"),
    ]:
        request = runner_request(resolved, case, role, "teacher_forced", forced, chosen)
        directory = output / label
        requests[label] = request
        execution = execute_runner(
            resolved.binaries[role],
            request,
            directory,
            resolved.target,
            resolved.plan.settings.timeout_seconds,
        )
        if execution["status"] != "complete":
            raise VFGError(f"replay failed: {label}")
        results[label] = validate_output(
            directory / "output", request, case.model_dump(), inputs[role], resolved.plan.settings
        )
        events[label] = capture_events(directory / "output/captures.jsonl")
    left = results["baseline-before"]
    right = results["candidate"]
    restored = results["baseline-after"]
    if (
        left[0]["logits_sha256"] != restored[0]["logits_sha256"]
        or events["baseline-before"] != events["baseline-after"]
    ):
        raise InsufficientEvidence("baseline did not restore after candidate replay")
    differences = compare_captures(
        events["baseline-before"],
        events["candidate"],
        output / "baseline-before/output",
        output / "candidate/output",
    )
    if not differences:
        raise InsufficientEvidence("output discrepancy did not localise to captured tensors")
    if left[0]["steps"][-1]["history_sha256"] != right[0]["steps"][-1]["history_sha256"]:
        raise InsufficientEvidence("replay histories differ")
    preserved = np.array_equal(x[step].view("<u4"), left[1][-1].view("<u4")) and np.array_equal(
        y[step].view("<u4"), right[1][-1].view("<u4")
    )
    if not preserved:
        raise InsufficientEvidence("instrumented replay did not preserve original discrepancy")
    layer_map = list(dict.fromkeys(e["name"] for e in events["baseline-before"]))
    result = {
        "schema_version": 1,
        "complete": True,
        "started_at": started,
        "finished_at": now(),
        "source_bundle_sha256": source["bundle_sha256"],
        "case_id": case_id,
        "capture": capture,
        "prediction_step": step,
        "first_free_run_token_difference": divergence,
        "history_sha256": left[0]["steps"][-1]["history_sha256"],
        "history_matched": True,
        "original_discrepancy_preserved": preserved,
        "baseline_restored": True,
        "injected_diagnostic": bool(inputs["candidate"].get("injection")),
        "injection": inputs["candidate"].get("injection"),
        "earliest_difference": differences[0],
        "difference_count": len(differences),
        "layer_map": layer_map,
        "source": None,
        "instruction_site": None,
        "mapping_limitation": "Observed tensor/operator boundary only; no instruction-level causal mapping.",
        "logit_numeric": numeric_errors(left[1][-1], right[1][-1]),
    }
    atomic_json(output / "inputs.json", inputs)
    atomic_json(output / "localisation.json", result)
    atomic_json(output / "differences.json", differences)
    seal_bundle(output)
    return result


def verify_localisation(root):
    root = Path(root)
    verify_bundle(root)
    saved = load_document(root / "localisation.json")
    inputs = load_document(root / "inputs.json")
    case = next(c for c in inputs["selected_cases"] if c["id"] == saved["case_id"])
    values = {}
    events = {}
    for label, role in [
        ("baseline-before", "baseline"),
        ("candidate", "candidate"),
        ("baseline-after", "baseline"),
    ]:
        directory = root / label
        request = load_document(directory / "request.json")
        values[label] = validate_output(
            directory / "output", request, case, inputs[role], Plan.model_validate(inputs["plan"]).settings
        )
        events[label] = capture_events(directory / "output/captures.jsonl")
    diff = compare_captures(
        events["baseline-before"],
        events["candidate"],
        root / "baseline-before/output",
        root / "candidate/output",
    )
    if (
        not diff
        or diff[0] != saved["earliest_difference"]
        or diff != load_document(root / "differences.json")
    ):
        raise VFGError("localisation does not rederive")
    if values["baseline-before"][0]["logits_sha256"] != values["baseline-after"][0]["logits_sha256"]:
        raise VFGError("baseline restoration failed")
    return saved
