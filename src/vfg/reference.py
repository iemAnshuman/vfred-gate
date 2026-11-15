"""Cross-machine comparison: record a reference on one machine, check a build on another.

`record` runs the baseline side only and seals its raw outputs. `check` copies those
outputs into a new qualification bundle, runs the candidate locally (teacher forcing uses
the recorded baseline tokens), and applies the same `assess` as `vfg compare`. The result
re-derives offline with `vfg verify`. Localisation needs both binaries on one machine, so
`check` reports the token step but does not localise.
"""

import json
from pathlib import Path
import platform

from .controller.qualification import ResolvedPlan, assess, runner_request
from .errors import InsufficientEvidence, VFGError
from .execute import execute_runner
from .manifest import atomic_json, file_digest, load_document, now
from .schema import CorpusCase, ModelLock, Plan, Settings, Stack, Verdict
from .store import safe_child, seal_bundle, verify_bundle
from .canary.corpus import freeze_corpus, read_corpus
from .workflow import ALLOWED, build_side, host_target, load_prompts, make_contract, model_lock

MODES = ("free_run", "teacher_forced_baseline")


def _run(resolved, case, role, mode, repeat, forced, root, relative, jobs):
    request = runner_request(
        resolved, case, role, "free_run" if mode == "free_run" else "teacher_forced", forced
    )
    try:
        execute_runner(
            resolved.binaries[role], request, root / relative, resolved.target, resolved.plan.settings.timeout_seconds
        )
    except InsufficientEvidence as exc:
        atomic_json(root / relative / "execution.json", {"status": "timeout", "reason": str(exc)})
    except VFGError as exc:
        atomic_json(root / relative / "execution.json", {"status": "error", "reason": str(exc)})
    jobs.append({"case_id": case.id, "role": role, "mode": mode, "repetition": repeat, "path": relative})


def _resolved(plan, lock, contract, target, stacks, cases):
    binaries = {role: Path(stack.binary) for role, stack in stacks.items()}
    return ResolvedPlan(plan, lock, Path(lock.filename), contract, target, stacks, binaries, cases, {})


def record(
    model,
    a="pinned",
    output=None,
    a_cmake=(),
    a_cflags=(),
    prompts=None,
    cases=16,
    repetitions=3,
    max_tokens=32,
    context=512,
    progress=print,
):
    """Run the baseline side only and seal a portable reference bundle."""
    if repetitions < 2:
        raise VFGError("repetitions must be at least 2 to detect nondeterminism")
    if max_tokens >= context:
        raise VFGError(f"--max-tokens ({max_tokens}) must be smaller than --context ({context})")
    output = Path(output or "runs/reference").resolve()
    if output.exists() and any(output.iterdir()):
        raise VFGError(f"output directory is not empty: {output}")
    setup = output / "setup"
    setup.mkdir(parents=True, exist_ok=True)
    lock = model_lock(model)
    atomic_json(setup / "model.lock.json", lock.model_dump())
    stack, info = build_side(a, a_cmake, a_cflags, label="baseline", progress=progress)
    rows = load_prompts(prompts, cases)
    (setup / "prompts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    freeze_corpus(setup / "prompts.jsonl", setup / "model.lock.json", Path(stack.binary), setup / "corpus.jsonl")
    corpus = read_corpus(setup / "corpus.jsonl")
    over = [c.id for c in corpus if len(c.tokens) + max_tokens > context]
    if over:
        raise VFGError(f"context budget exceeded for {', '.join(over[:5])}; raise --context or lower --max-tokens")
    # Keep the baseline's build record as evidence; machine B cannot rebuild it.
    (setup / "build-manifest.json").write_bytes(Path(stack.build_manifest).read_bytes())
    settings = Settings(context=context, max_tokens=max_tokens)
    target = host_target()
    plan = Plan(
        id=output.name, model="-", corpus="-", contract="-", baseline="-", candidate="-", target="-",
        settings=settings,
    )
    resolved = _resolved(plan, lock, make_contract("decision", len(rows), repetitions), target,
                         {"baseline": stack}, corpus)
    jobs = []
    for n, case in enumerate(corpus):
        forced = None
        for mode in MODES:
            for repeat in range(repetitions):
                relative = f"jobs/c{n:03d}/{mode}/baseline/r{repeat:03d}"
                _run(resolved, case, "baseline", mode, repeat, None if mode == "free_run" else forced, output, relative, jobs)
                if mode == "free_run" and repeat == 0:
                    result = output / relative / "output/result.json"
                    if not result.exists():
                        raise VFGError(f"baseline run failed for {case.id}; see {output / relative}")
                    forced = load_document(result)["selected_tokens"]
        progress(f"{n + 1}/{len(corpus)} cases recorded")
    atomic_json(
        output / "reference.json",
        {
            "schema_version": 1,
            "recorded_at": now(),
            "model": lock.model_dump(),
            "baseline": stack.model_dump(),
            "baseline_source": info,
            "target": target.model_dump(),
            "platform": platform.platform(),
            "settings": settings.model_dump(),
            "repetitions": repetitions,
            "cases": [c.model_dump() for c in corpus],
            "jobs": jobs,
        },
    )
    seal_bundle(output)
    return {"reference": str(output), "cases": len(corpus), "jobs": len(jobs)}


def check(
    reference,
    model,
    b="pinned",
    output=None,
    b_cmake=(),
    b_cflags=(),
    contract="decision",
    progress=print,
    reference_sha256=None,
):
    """Run the candidate locally and judge it against a sealed reference.

    The reference is trusted as given unless `reference_sha256` pins its bundle index.
    """
    reference = Path(reference).resolve()
    index = verify_bundle(reference, reference_sha256)["index"]["files"]
    ref = load_document(reference / "reference.json")
    lock = ModelLock.model_validate(ref["model"])
    local = model_lock(model)
    if local.sha256 != lock.sha256:
        raise VFGError("model differs from the one in the reference")
    lock = local
    output = Path(output or "runs/check").resolve()
    if output.exists() and any(output.iterdir()):
        raise VFGError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    base = Stack.model_validate(ref["baseline"])
    # References recorded before the manifest was copied have none; verify it when present.
    manifest_state = "absent"
    if "setup/build-manifest.json" in index:
        if file_digest(reference / "setup/build-manifest.json") != base.build_manifest_sha256:
            raise VFGError("reference build manifest does not match the baseline stack")
        manifest_state = "verified"
    cand, info = build_side(b, b_cmake, b_cflags, label="candidate", progress=progress)
    cases = [CorpusCase.model_validate(c) for c in ref["cases"]]
    repetitions = ref["repetitions"]
    settings = Settings.model_validate(ref["settings"])
    rules = make_contract(contract, len(cases), repetitions)
    target = host_target()
    plan = Plan(
        id=output.name, model="-", corpus="-", contract="-", baseline="-", candidate="-", target="-",
        settings=settings,
        allowed_stack_differences=[k for k in ALLOWED if base.model_dump()[k] != cand.model_dump()[k]],
    )
    modes = ["free_run"] + (
        ["teacher_forced_baseline"] if any(r.alignment == "teacher_forced_baseline" for r in rules.rules) else []
    )
    jobs = []
    case_index = {c.id: n for n, c in enumerate(cases)}
    if len(case_index) != len(cases):
        raise VFGError("reference has duplicate case ids")
    expected_jobs = {
        f"jobs/c{n:03d}/{mode}/baseline/r{r:03d}": (c.id, mode, r)
        for n, c in enumerate(cases)
        for mode in MODES
        for r in range(repetitions)
    }
    seen = set()
    for job in ref["jobs"]:
        key = (job.get("case_id"), job.get("mode"), job.get("repetition"))
        # Each job path must be the one record() writes for its case, mode and repetition, once.
        if (
            job.get("role") != "baseline"
            or job.get("case_id") not in case_index
            or expected_jobs.get(job.get("path")) != key
            or job["path"] in seen
        ):
            raise VFGError(f"unexpected job in reference: {job.get('path')}")
        seen.add(job["path"])
        if job["mode"] not in modes:
            continue
        prefix = job["path"] + "/"
        # Copy only indexed regular files; verify_bundle already checked their bytes.
        for name in index:
            if name.startswith(prefix):
                source = safe_child(reference, name)
                if source.is_symlink():
                    raise VFGError(f"symlink in reference: {name}")
                target_path = output / name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(source.read_bytes())
        jobs.append(job)
    resolved = _resolved(plan, lock, rules, target, {"baseline": base, "candidate": cand}, cases)
    paths = {(j["case_id"], j["mode"], j["repetition"]): j["path"] for j in jobs}
    for n, case in enumerate(cases):
        if (case.id, "free_run", 0) not in paths:
            raise VFGError(f"reference has no free_run r000 job for {case.id}")
        base_result = output / paths[(case.id, "free_run", 0)] / "output/result.json"
        forced = load_document(base_result)["selected_tokens"] if base_result.exists() else None
        for mode in modes:
            if mode != "free_run" and forced is None:
                continue
            for repeat in range(repetitions):
                relative = f"jobs/c{n:03d}/{mode}/candidate/r{repeat:03d}"
                _run(resolved, case, "candidate", mode, repeat, forced if mode != "free_run" else None,
                     output, relative, jobs)
        progress(f"{n + 1}/{len(cases)} cases checked")
    inputs = {
        "plan": plan.model_dump(),
        "model": lock.model_dump(),
        "contract": rules.model_dump(),
        "target": target.model_dump(),
        "model_path": lock.filename,
        "baseline": base.model_dump(),
        "candidate": cand.model_dump(),
        "corpus": [c.model_dump() for c in cases],
        "selected_cases": [c.model_dump() for c in cases],
        "binaries": {"baseline": base.binary, "candidate": cand.binary},
        "reference": {
            "bundle_sha256": file_digest(reference / "bundle.json"),
            "platform": ref["platform"],
            "target": ref["target"],
            "baseline_source": ref["baseline_source"],
            "build_manifest": manifest_state,
        },
        "candidate_source": info,
        "candidate_platform": platform.platform(),
    }
    atomic_json(output / "inputs.json", inputs)
    try:
        verdict, margins = assess(output, inputs, jobs)
    except (VFGError, OSError, ValueError, KeyError, TypeError) as exc:
        verdict, margins = Verdict(verdict="ERROR", exit_code=4, reasons=[str(exc)]), {}
    atomic_json(output / "margins.json", margins)
    atomic_json(
        output / "run.json",
        {"schema_version": 1, "started_at": ref["recorded_at"], "finished_at": now(), "complete": True, "jobs": jobs},
    )
    atomic_json(output / "verdict.json", verdict.model_dump())
    seal_bundle(output)
    return {
        "verdict": verdict.verdict,
        "exit_code": verdict.exit_code,
        "reasons": verdict.reasons,
        "rules": [
            {k: r.get(k) for k in ("id", "metric", "value", "operator", "threshold", "passed")} for r in verdict.rules
        ],
        "first_divergences": verdict.rules[0]["first_divergences"] if verdict.rules else [],
        "reference_platform": ref["platform"],
        "candidate_platform": platform.platform(),
        "qualification": str(output),
    }
