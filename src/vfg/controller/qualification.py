"""Fresh-process qualification and raw-evidence verdict reconstruction."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import struct
import numpy as np
from ..canary.corpus import read_corpus
from ..canary.margins import top_two_margins
from ..compare.metrics import compare_rule
from ..contracts.engine import evaluate_contract
from ..errors import VFGError, InsufficientEvidence
from ..execute import execute_runner
from ..manifest import atomic_json, diff_manifests, file_digest, load_document, now, resolve
from ..schema import Plan, ModelLock, Contract, Stack, Target, Verdict
from ..store import read_array, safe_child, seal_bundle, verify_bundle


@dataclass
class ResolvedPlan:
    plan: Plan
    model: ModelLock
    model_path: Path
    contract: Contract
    target: Target
    stacks: dict
    binaries: dict
    cases: list
    inputs: dict


def resolve_plan(path):
    path = Path(path).resolve()
    plan = load_document(path, Plan)
    paths = {
        k: resolve(path.parent, getattr(plan, k))
        for k in ("model", "corpus", "contract", "target", "baseline", "candidate")
    }
    model = load_document(paths["model"], ModelLock)
    model_path = paths["model"].parent / model.filename
    if (
        not model_path.is_file()
        or model_path.stat().st_size != model.size_bytes
        or file_digest(model_path) != model.sha256
    ):
        raise VFGError("missing or corrupt pinned model")
    contract = load_document(paths["contract"], Contract)
    target = load_document(paths["target"], Target)
    stacks = {}
    binaries = {}
    inputs = {
        "plan": plan.model_dump(),
        "model": model.model_dump(),
        "contract": contract.model_dump(),
        "target": target.model_dump(),
        "model_path": str(model_path),
        "input_sha256": {k: file_digest(v) for k, v in paths.items()},
        "plan_sha256": file_digest(path),
    }
    for role in ("baseline", "candidate"):
        stack = load_document(paths[role], Stack)
        binary = resolve(paths[role].parent, stack.binary)
        if not binary.is_file() or file_digest(binary) != stack.binary_sha256:
            raise VFGError(f"{role} binary identity mismatch")
        if not stack.build_manifest:
            raise VFGError(f"{role} requires a build manifest")
        build_path = resolve(paths[role].parent, stack.build_manifest)
        if file_digest(build_path) != stack.build_manifest_sha256:
            raise VFGError(f"{role} build manifest identity mismatch")
        build = load_document(build_path)
        if (
            build["binary_sha256"] != stack.binary_sha256
            or build["source_digest"] != stack.source_digest
            or build["source_revision"] != stack.source_revision
        ):
            raise VFGError(f"{role} build and stack identities disagree")
        stacks[role] = stack
        binaries[role] = binary
        inputs[role] = stack.model_dump()
        inputs[role + "_build"] = build
    cases = read_corpus(paths["corpus"])
    inputs["corpus"] = [c.model_dump() for c in cases]
    if plan.cases is not None:
        mapping = {c.id: c for c in cases}
        if set(plan.cases) - mapping.keys():
            raise VFGError("requested case missing from frozen corpus")
        cases = [mapping[c] for c in plan.cases]
    if any(c.model_sha256 != model.sha256 for c in cases):
        raise VFGError("corpus/model identity mismatch")
    if any(len(c.tokens) + plan.settings.max_tokens > plan.settings.context for c in cases):
        raise VFGError("context budget exceeded")
    inputs["selected_cases"] = [c.model_dump() for c in cases]
    inputs["binaries"] = {k: str(v) for k, v in binaries.items()}
    return ResolvedPlan(plan, model, model_path, contract, target, stacks, binaries, cases, inputs)


def runner_request(resolved, case, role, mode="free_run", forced=None, capture=None):
    settings = resolved.plan.settings
    request = {
        "schema_version": 1,
        "case_id": case.id,
        "mode": mode,
        "model_path": str(resolved.model_path),
        "model_sha256": resolved.model.sha256,
        "prompt_tokens": case.tokens,
        "context": settings.context,
        "max_tokens": settings.max_tokens,
        "capture": capture or settings.capture.model_dump(),
    }
    if forced is not None:
        request.update(forced_tokens=forced, max_tokens=len(forced))
    injection = resolved.stacks[role].injection
    if injection is not None:
        request["injection"] = injection.model_dump()
    return request


def _history(tokens):
    return hashlib.sha256(struct.pack("<" + "i" * len(tokens), *tokens)).hexdigest()


def validate_output(root, request, case, stack, settings):
    root = Path(root)
    result = load_document(root / "result.json")
    if result.get("complete") is not True or result.get("schema_version") != 1:
        raise VFGError("missing completion marker")
    for k in ("case_id", "mode", "prompt_tokens", "context"):
        if result.get(k) != request[k]:
            raise VFGError(f"output does not match request: {k}")
    if (
        result["model"]["model_sha256"] != request["model_sha256"]
        or result["model"]["chat_template_sha256"] != case["tokenizer_sha256"]
    ):
        raise VFGError("output model/tokenizer identity mismatch")
    if result["model"]["diagnostic_build"] != (stack["build_class"] == "diagnostic"):
        raise VFGError("build class mismatch")
    if result.get("threads") != 1 or result.get("kv_type") != "f32":
        raise VFGError("uncontrolled runtime settings")
    if result.get("injection_count") != (1 if stack.get("injection") else 0):
        raise VFGError("injection execution count mismatch")
    if result.get("forced_tokens") != request.get("forced_tokens", []):
        raise VFGError("forced continuation mismatch")
    a = read_array(root, result)
    tokens = result["selected_tokens"]
    steps = result["steps"]
    if not 1 <= len(tokens) <= request["max_tokens"] or a.shape != (
        len(tokens),
        result["model"]["vocab_size"],
    ):
        raise VFGError("output length/shape mismatch")
    if not np.isfinite(a).all():
        raise InsufficientEvidence("non-finite logits")
    if np.argmax(a, axis=1).tolist() != tokens:
        raise VFGError("greedy choices do not match logits")
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    if events != steps or len(steps) != len(tokens):
        raise VFGError("missing or altered output events")
    history = list(request["prompt_tokens"])
    forced = request.get("forced_tokens", tokens)
    for i, event in enumerate(steps):
        expected = {
            "step": i,
            "history_sha256": _history(history),
            "selected_token": tokens[i],
            "offset_bytes": i * a.shape[1] * 4,
            "shape": [a.shape[1]],
            "dtype": "<f4",
        }
        if event != expected:
            raise VFGError("invalid event identity, offset, or history")
        if i + 1 < len(steps):
            history.append(forced[i])
    allowed = {"token_budget", "eos"} if request["mode"] == "free_run" else {"token_budget"}
    if result["stop_reason"] not in allowed:
        raise VFGError("unsupported stop reason")
    if result["stop_reason"] == "token_budget" and len(tokens) != request["max_tokens"]:
        raise VFGError("incomplete token budget")
    captures = [json.loads(line) for line in (root / "captures.jsonl").read_text().splitlines()]
    if len(captures) != result["capture_events"]:
        raise VFGError("capture count mismatch")
    for i, event in enumerate(captures):
        if event["ordinal"] != i:
            raise VFGError("reordered captures")
        pos = event["position"]
        h = request["prompt_tokens"][: pos + 1]
        if pos >= len(request["prompt_tokens"]):
            h = request["prompt_tokens"] + forced[: pos + 1 - len(request["prompt_tokens"])]
        if event["history_sha256"] != _history(h):
            raise VFGError("capture history mismatch")
        if "payload" in event:
            p = safe_child(root, event["payload"])
            if file_digest(p) != event["sha256"] or p.stat().st_size != int(np.prod(event["shape"])) * 4:
                raise VFGError("capture payload integrity mismatch")
    return result, a


def assess(root, inputs, jobs):
    root = Path(root)
    plan = Plan.model_validate(inputs["plan"])
    contract = Contract.model_validate(inputs["contract"])
    cases = inputs["selected_cases"]
    diff = diff_manifests(inputs["baseline"], inputs["candidate"], plan.allowed_stack_differences)
    evidence = {
        "errors": [],
        "insufficient": [],
        "distinct_cases": len(cases),
        "required_repetitions": contract.evidence.repetitions,
        "execution_class": inputs["target"]["execution_class"],
        "manifest_diff": diff,
        "completed_jobs": 0,
        "diagnostic_injection": bool(inputs["candidate"].get("injection")),
        "stability": [],
    }
    if diff["uncontrolled"]:
        evidence["insufficient"].append("unplanned stack differences")
    if len(cases) < contract.evidence.minimum_cases:
        evidence["insufficient"].append("too few independent cases")
    modes = ["free_run"] + (
        ["teacher_forced_baseline"]
        if any(r.alignment == "teacher_forced_baseline" for r in contract.rules)
        else []
    )
    indexed = {}
    for job in jobs:
        key = (job["case_id"], job["role"], job["mode"], job["repetition"])
        if key in indexed:
            evidence["errors"].append("duplicate execution identity")
        indexed[key] = job
    expected = {
        (c["id"], r, m, n)
        for c in cases
        for r in ("baseline", "candidate")
        for m in modes
        for n in range(contract.evidence.repetitions)
    }
    if set(indexed) - expected:
        evidence["errors"].append("unexpected execution identities")
    if expected - set(indexed):
        evidence["insufficient"].append("required executions missing")
    valid = {}
    margins = {}
    for case in cases:
        for role in ("baseline", "candidate"):
            for mode in modes:
                repeated = []
                for n in range(contract.evidence.repetitions):
                    key = (case["id"], role, mode, n)
                    job = indexed.get(key)
                    if not job:
                        continue
                    directory = safe_child(root, job["path"])
                    try:
                        execution = load_document(directory / "execution.json")
                        if execution["status"] == "timeout":
                            raise InsufficientEvidence("execution timed out")
                        if execution["status"] != "complete" or execution["returncode"] != 0:
                            raise VFGError("runner execution failed")
                        if (
                            execution["binary_sha256"] != inputs[role]["binary_sha256"]
                            or execution["execution_class"] != inputs["target"]["execution_class"]
                        ):
                            raise VFGError("executor identity mismatch")
                        if inputs["target"]["require_affinity"] and not execution["affinity"]["applied"]:
                            raise InsufficientEvidence("required affinity not applied")
                        request = load_document(directory / "request.json")
                        if (
                            request["case_id"] != case["id"]
                            or request["prompt_tokens"] != case["tokens"]
                            or request["model_sha256"] != inputs["model"]["sha256"]
                        ):
                            raise VFGError("job does not match frozen inputs")
                        if request.get("injection") != inputs[role].get("injection"):
                            raise VFGError("undeclared injection")
                        if (
                            request["context"] != plan.settings.context
                            or request["capture"] != plan.settings.capture.model_dump()
                        ):
                            raise VFGError("job settings mismatch")
                        if mode == "free_run":
                            if (
                                request["mode"] != "free_run"
                                or request["max_tokens"] != plan.settings.max_tokens
                            ):
                                raise VFGError("wrong free-run request")
                        else:
                            base = valid.get((case["id"], "baseline", "free_run", 0))
                            if base is None:
                                raise InsufficientEvidence("baseline unavailable for teacher forcing")
                            if (
                                request["mode"] != "teacher_forced"
                                or request.get("forced_tokens") != base[0]["selected_tokens"]
                                or request["max_tokens"] != len(base[0]["selected_tokens"])
                            ):
                                raise VFGError("teacher forcing does not use baseline continuation")
                        item = validate_output(
                            directory / "output", request, case, inputs[role], plan.settings
                        )
                        valid[key] = item
                        repeated.append(item[0])
                        evidence["completed_jobs"] += 1
                    except InsufficientEvidence as exc:
                        evidence["insufficient"].append(f"{key}: {exc}")
                    except (VFGError, OSError, KeyError, ValueError, TypeError) as exc:
                        evidence["errors"].append(f"{key}: {exc}")
                signatures = {
                    (x["logits_sha256"], tuple(x["selected_tokens"]), x["stop_reason"]) for x in repeated
                }
                stable = len(signatures) == 1 and len(repeated) == contract.evidence.repetitions
                evidence["stability"].append(
                    {
                        "case_id": case["id"],
                        "role": role,
                        "mode": mode,
                        "stable": stable,
                        "repetitions": len(repeated),
                    }
                )
                if not stable:
                    evidence["insufficient"].append(
                        f"{case['id']}/{role}/{mode}: incomplete or unstable repetitions"
                    )
        base = valid.get((case["id"], "baseline", "free_run", 0))
        if base:
            values = top_two_margins(base[1])
            margins[case["id"]] = {
                "minimum": float(values.min()),
                "mean": float(values.mean()),
                "per_step": values.tolist(),
            }
    metrics = []
    for rule in contract.rules:
        pairs = []
        for case in cases:
            a = valid.get((case["id"], "baseline", rule.alignment, 0))
            b = valid.get((case["id"], "candidate", rule.alignment, 0))
            if a and b:
                pairs.append((a[0], b[0], a[1], b[1]))
        try:
            metrics.append(compare_rule(rule, pairs))
        except InsufficientEvidence as exc:
            evidence["insufficient"].append(str(exc))
        except VFGError as exc:
            evidence["errors"].append(str(exc))
    return evaluate_contract(contract, evidence, metrics), margins


def qualify(plan_path, output, progress=None):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise VFGError("qualification output is not empty")
    output.mkdir(parents=True, exist_ok=True)
    started = now()
    jobs = []
    try:
        resolved = resolve_plan(plan_path)
        inputs = resolved.inputs
        atomic_json(output / "inputs.json", inputs)
        worst = (
            len(resolved.cases)
            * 2
            * resolved.contract.evidence.repetitions
            * resolved.plan.settings.max_tokens
            * 49152
            * 4
        )
        if shutil.disk_usage(output).free < worst * 2 + 200_000_000:
            raise VFGError("insufficient free disk for full evidence")
        for case_no, case in enumerate(resolved.cases):
            forced = None
            modes = ["free_run"] + (
                ["teacher_forced_baseline"]
                if any(r.alignment == "teacher_forced_baseline" for r in resolved.contract.rules)
                else []
            )
            for mode in modes:
                if mode != "free_run" and forced is None:
                    continue
                for role in ("baseline", "candidate"):
                    for repeat in range(resolved.contract.evidence.repetitions):
                        relative = f"jobs/c{case_no:03d}/{mode}/{role}/r{repeat:03d}"
                        request = runner_request(
                            resolved,
                            case,
                            role,
                            "free_run" if mode == "free_run" else "teacher_forced",
                            forced if mode != "free_run" else None,
                        )
                        try:
                            execute_runner(
                                resolved.binaries[role],
                                request,
                                output / relative,
                                resolved.target,
                                resolved.plan.settings.timeout_seconds,
                            )
                        except InsufficientEvidence as exc:
                            atomic_json(
                                output / relative / "execution.json",
                                {"status": "timeout", "reason": str(exc)},
                            )
                        except VFGError as exc:
                            atomic_json(
                                output / relative / "execution.json", {"status": "error", "reason": str(exc)}
                            )
                        jobs.append(
                            {
                                "case_id": case.id,
                                "role": role,
                                "mode": mode,
                                "repetition": repeat,
                                "path": relative,
                            }
                        )
                        if mode == "free_run" and role == "baseline" and repeat == 0:
                            result_path = output / relative / "output/result.json"
                            if result_path.exists():
                                forced = load_document(result_path)["selected_tokens"]
            if progress:
                progress(f"{case_no + 1}/{len(resolved.cases)} cases executed")
        verdict, margins = assess(output, inputs, jobs)
        atomic_json(output / "margins.json", margins)
    except (VFGError, OSError, ValueError, KeyError, TypeError) as exc:
        verdict = Verdict(verdict="ERROR", exit_code=4, reasons=[str(exc)])
    atomic_json(
        output / "run.json",
        {"schema_version": 1, "started_at": started, "finished_at": now(), "complete": True, "jobs": jobs},
    )
    atomic_json(output / "verdict.json", verdict.model_dump())
    seal_bundle(output)
    return verdict


def rederive(root):
    root = Path(root)
    verified = verify_bundle(root)
    # Reject unindexed additions as well as corrupt/missing indexed bytes.
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and p.name not in ("bundle.json", "bundle.sha256")
        and not p.relative_to(root).as_posix().startswith("report/")
    }
    if actual != set(verified["index"]["files"]):
        raise VFGError("unindexed or missing evidence files")
    run = load_document(root / "run.json")
    if run.get("complete") is not True:
        raise VFGError("incomplete qualification bundle")
    if not (root / "inputs.json").exists():
        raise VFGError("input validation failed; no numerical verdict to rederive")
    verdict, margins = assess(root, load_document(root / "inputs.json"), run["jobs"])
    saved = load_document(root / "verdict.json", Verdict)
    if saved.model_dump() != verdict.model_dump():
        raise VFGError("saved verdict differs from raw-evidence reconstruction")
    if margins != load_document(root / "margins.json"):
        raise VFGError("saved margins differ from raw evidence")
    return {
        "verified": True,
        "bundle_sha256": verified["bundle_sha256"],
        "verdict": verdict.model_dump(),
        "margins": margins,
    }
