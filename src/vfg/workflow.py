"""`vfg compare`: build two llama.cpp sides, qualify them, explain a FAIL, render a report."""

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import os
import platform
import shutil
import subprocess

from .assets import native_root
from .build import build_runner, c_compiler_name
from .canary.corpus import freeze_corpus
from .controller import qualify, rederive
from .errors import InsufficientEvidence, VFGError
from .manifest import atomic_json, digest, file_digest, load_document, now
from .schema import Contract, ModelLock, Plan, Stack, Target
from .sources import cache_root, resolve_side

PRESETS = {
    "bit": [
        {"id": "bits", "metric": "bit_equal_rate", "alignment": "free_run", "operator": "ge", "threshold": 1.0},
        {"id": "sequence", "metric": "sequence_exact_match_rate", "operator": "ge", "threshold": 1.0},
    ],
    "decision": [
        {
            "id": "token_choice",
            "metric": "argmax_agreement_rate",
            "alignment": "teacher_forced_baseline",
            "operator": "ge",
            "threshold": 1.0,
        },
        {"id": "sequence", "metric": "sequence_exact_match_rate", "operator": "ge", "threshold": 1.0},
    ],
    "sequence": [
        {"id": "sequence", "metric": "sequence_exact_match_rate", "operator": "ge", "threshold": 1.0},
    ],
}

# A comparison declares that the two builds may differ in every build identity.
ALLOWED = [
    "source_revision",
    "source_digest",
    "reduction_policy",
    "binary",
    "binary_sha256",
    "compiler",
    "flags",
    "build_manifest",
    "build_manifest_sha256",
]


def make_contract(preset, cases, repetitions):
    if preset not in PRESETS:
        raise VFGError(f"unknown contract preset {preset!r}; choose from {', '.join(PRESETS)}")
    return Contract(
        id=f"{preset}-n{cases}-r{repetitions}",
        compatibility_level=preset,
        rules=PRESETS[preset],
        evidence={"minimum_cases": cases, "repetitions": repetitions},
    )


def load_prompts(path=None, cases=16):
    """Return prompt rows in corpus-source form; plain text files hold one prompt per line."""
    if path is None:
        path = native_root() / "corpora/source/pilot.jsonl"
    path = Path(path)
    text = path.read_text()
    rows = []
    if path.suffix == ".jsonl":
        for n, line in enumerate(x for x in text.splitlines() if x.strip()):
            item = json.loads(line)
            if not isinstance(item.get("text"), str) or not item["text"].strip():
                raise VFGError(f"prompt {n + 1} has no text")
            rows.append({"id": str(item.get("id", f"p{n + 1:03d}")), "text": item["text"]})
    else:
        rows = [{"id": f"p{n + 1:03d}", "text": x} for n, x in enumerate(t for t in text.splitlines() if t.strip())]
    if cases is not None:
        rows = rows[:cases]
    if not rows:
        raise VFGError("no prompts")
    return [
        {"id": r["id"], "group_id": r["id"], "category": "prompt", "split": "exploratory", "text": r["text"]}
        for r in rows
    ]


def model_lock(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise VFGError(f"model not found: {path}")
    with path.open("rb") as f:
        if f.read(4) != b"GGUF":
            raise VFGError(f"not a GGUF file: {path}")
    return ModelLock(
        repository="local",
        filename=str(path),
        sha256=file_digest(path),
        quantisation=path.stem.rsplit("-", 1)[-1] if "-" in path.stem else "unknown",
        size_bytes=path.stat().st_size,
    )


def host_target():
    return Target(
        id="host-cpu",
        execution_class="host",
        architecture=platform.machine(),
        description=f"{platform.system()} {platform.machine()} CPU, one thread",
    )


@contextmanager
def _locked(path):
    """Hold an exclusive lock so parallel runs never build into the same cache directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _tool(path):
    version = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30)
    return {
        "path": str(path),
        "version": (version.stdout or version.stderr).strip(),
        "sha256": file_digest(Path(path).resolve()),
    }


def toolchain(compiler=None):
    """Identity of the tools a build would use; part of the build cache key."""
    env = {k: os.environ.get(k) for k in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "SDKROOT")}
    ident = {"env": env}
    commands = [("cxx", env["CXX"] or "c++"), ("cc", env["CC"] or "cc"), ("cmake", "cmake")]
    if compiler is not None:
        # An explicit compiler replaces CC/CXX; fingerprint it so an upgrade in place rebuilds.
        cxx = Path(compiler).absolute()
        commands[:2] = [("cxx", str(cxx)), ("cc", str(cxx.with_name(c_compiler_name(cxx.name))))]
    for name, command in commands:
        path = shutil.which(command)
        ident[name] = _tool(path) if path else None
    return ident


def build_side(spec, cmake_args=(), cflags=(), compiler=None, label="side", progress=print):
    """Build (or reuse from cache) the runner for one side; return a Stack and its manifest."""
    tree, commit, identity = resolve_side(spec)
    root = native_root()
    key = digest(
        {
            "identity": identity,
            "cmake_args": list(cmake_args),
            "cflags": list(cflags),
            "toolchain": toolchain(compiler),
            # A dirty checkout is rebuilt every run, in its own directory per side.
            "dirty_label": label if identity.get("dirty") else None,
            "native": {
                p.relative_to(root).as_posix(): file_digest(p)
                for d in ("runner", "microbench")
                for p in sorted((root / d).rglob("*"))
                if p.is_file()
            }
            | {"CMakeLists.txt": file_digest(root / "CMakeLists.txt")},
            "platform": platform.platform(),
        }
    )
    build_dir = cache_root() / "builds" / key[:20]
    manifest_path = build_dir / "build-manifest.json"
    binary = build_dir / "runner/vfg-llama-runner"
    with _locked(build_dir.with_name(build_dir.name + ".lock")):
        reuse = (
            not identity.get("dirty")
            and manifest_path.is_file()
            and binary.is_file()
            and load_document(manifest_path).get("binary_sha256") == file_digest(binary)
        )
        if reuse:
            progress(f"[{label}] reusing cached build {build_dir.name}")
            manifest = load_document(manifest_path)
        else:
            if build_dir.exists():
                shutil.rmtree(build_dir)
            progress(f"[{label}] building llama.cpp {commit[:12]} ({identity['kind']}) ...")
            manifest = build_runner(
                build_dir,
                tree,
                commit,
                root=root,
                compiler=compiler,
                extra_flags=list(cflags),
                cmake_args=list(cmake_args),
                llama_source=identity,
                reduction_policy="native",
            )
    stack = Stack(
        id=label,
        source_revision=commit,
        source_digest=manifest["source_digest"],
        binary=str(binary),
        binary_sha256=manifest["binary_sha256"],
        compiler=manifest["compiler"],
        flags=["-O2", "-g", "-fno-fast-math", "-ffp-contract=off", *cflags, *cmake_args],
        build_manifest=str(manifest_path),
        build_manifest_sha256=file_digest(manifest_path),
        reduction_policy="native",
    )
    return stack, {"spec": spec, "identity": identity, "build_dir": str(build_dir)}


def differing_case(qualification):
    """First case whose free-run baseline and candidate outputs differ in tokens, then in bits."""
    verdict = load_document(qualification / "verdict.json")
    for rule in verdict.get("rules", []):
        for item in rule.get("first_divergences", []):
            if item["position"] is not None:
                return item["case_id"]
    run = load_document(qualification / "run.json")
    outputs = {}
    for job in run["jobs"]:
        if job["mode"] == "free_run" and job["repetition"] == 0:
            result = qualification / job["path"] / "output/result.json"
            if result.exists():
                outputs.setdefault(job["case_id"], {})[job["role"]] = load_document(result)["logits_sha256"]
    for case_id, pair in outputs.items():
        if len(pair) == 2 and pair["baseline"] != pair["candidate"]:
            return case_id
    return None


def explain(qualification, output, progress=print):
    """Localise the first observed difference to a layer and ggml op; never guess."""
    from .legal.matmul import assess_difference
    from .replay import localise

    qualification = Path(qualification).resolve()
    case_id = differing_case(qualification)
    if case_id is None:
        return {"status": "no_difference", "case_id": None}
    verdict = load_document(qualification / "verdict.json")
    token_step = next(
        (
            item["position"]
            for rule in verdict.get("rules", [])
            for item in rule.get("first_divergences", [])
            if item["case_id"] == case_id and item["position"] is not None
        ),
        None,
    )
    progress(f"[explain] localising case {case_id} to a layer and operator ...")
    try:
        result = localise(qualification, case_id, "operator", Path(output))
    except InsufficientEvidence as exc:
        return {"status": "not_aligned", "case_id": case_id, "first_token_difference": token_step, "reason": str(exc)}
    except (VFGError, OSError, KeyError, ValueError) as exc:
        return {"status": "error", "case_id": case_id, "first_token_difference": token_step, "reason": str(exc)}
    first = result["earliest_difference"]
    bundle = Path(output).resolve()
    try:
        legality = assess_difference(
            first, bundle / "baseline-before/output", bundle / "candidate/output", load_document(qualification / "inputs.json")["model_path"]
        )
    except (VFGError, OSError, KeyError, ValueError) as exc:
        legality = {"status": "not_assessed", "reason": str(exc)}
    return {
        "status": "localised",
        "case_id": case_id,
        "prediction_step": result["prediction_step"],
        "first_token_difference": result["first_free_run_token_difference"],
        "tensor": first["name"],
        "op": first["op"],
        "position": first["position"],
        "numeric": first.get("numeric"),
        "difference_count": result["difference_count"],
        "legality": legality,
        "bundle": str(Path(output).resolve()),
    }


def compare(
    model,
    a="pinned",
    b="pinned",
    output=None,
    a_cmake=(),
    b_cmake=(),
    a_cflags=(),
    b_cflags=(),
    contract="decision",
    prompts=None,
    cases=16,
    repetitions=3,
    max_tokens=32,
    context=512,
    run_explain=True,
    progress=print,
    a_compiler=None,
    b_compiler=None,
):
    if repetitions < 2:
        raise VFGError("repetitions must be at least 2 to detect nondeterminism")
    if max_tokens >= context:
        raise VFGError(f"--max-tokens ({max_tokens}) must be smaller than --context ({context})")
    output = Path(output or f"runs/compare-{now().replace(':', '').replace('+0000', 'Z')[:17]}").resolve()
    if output.exists() and any(output.iterdir()):
        raise VFGError(f"output directory is not empty: {output}")
    setup = output / "setup"
    setup.mkdir(parents=True, exist_ok=True)
    lock = model_lock(model)
    atomic_json(setup / "model.lock.json", lock.model_dump())
    base, base_info = build_side(a, a_cmake, a_cflags, a_compiler, label="baseline", progress=progress)
    cand, cand_info = build_side(b, b_cmake, b_cflags, b_compiler, label="candidate", progress=progress)
    atomic_json(setup / "baseline.json", base.model_dump())
    atomic_json(setup / "candidate.json", cand.model_dump())
    source = setup / "prompts.jsonl"
    rows = load_prompts(prompts, cases)
    source.write_text("".join(json.dumps(r) + "\n" for r in rows))
    progress(f"[setup] tokenising {len(rows)} prompts with the baseline build ...")
    freeze_corpus(source, setup / "model.lock.json", Path(base.binary), setup / "corpus.jsonl")
    atomic_json(setup / "contract.json", make_contract(contract, len(rows), repetitions).model_dump())
    atomic_json(setup / "target.json", host_target().model_dump())
    plan = Plan(
        id=output.name,
        model="model.lock.json",
        corpus="corpus.jsonl",
        contract="contract.json",
        baseline="baseline.json",
        candidate="candidate.json",
        target="target.json",
        allowed_stack_differences=[k for k in ALLOWED if base.model_dump()[k] != cand.model_dump()[k]],
        settings={"context": context, "max_tokens": max_tokens},
    )
    atomic_json(setup / "plan.json", plan.model_dump())
    progress(f"[qualify] {len(rows)} prompts x 2 builds x {repetitions} repetitions ...")
    verdict = qualify(setup / "plan.json", output / "qualification", progress)
    explanation = None
    if verdict.verdict == "FAIL" and run_explain:
        explanation = explain(output / "qualification", output / "explain", progress)
    from .report import render_report

    localisation = output / "explain" if explanation and explanation["status"] == "localised" else None
    report = None
    report_error = None
    if verdict.verdict in ("PASS", "FAIL"):
        try:
            report = render_report(output / "qualification", output / "report", localisation)
        except (VFGError, OSError, KeyError, ValueError) as exc:
            report_error = str(exc)
    summary = {
        "schema_version": 1,
        "verdict": verdict.verdict,
        "exit_code": verdict.exit_code,
        "reasons": verdict.reasons,
        "rules": [
            {k: r.get(k) for k in ("id", "metric", "value", "operator", "threshold", "passed")}
            for r in verdict.rules
        ],
        "model": {"path": lock.filename, "sha256": lock.sha256},
        "baseline": base_info,
        "candidate": cand_info,
        "contract": contract,
        "explain": explanation,
        "report": str(report) if report else None,
        "report_error": report_error,
        "qualification": str(output / "qualification"),
    }
    if verdict.verdict in ("PASS", "FAIL"):
        summary["bundle_sha256"] = rederive(output / "qualification")["bundle_sha256"]
    atomic_json(output / "summary.json", summary)
    return summary


def format_summary(summary):
    """Short human-readable result for the terminal."""
    lines = [f"{summary['verdict']}"]
    for rule in summary.get("rules", []):
        lines.append(f"  {rule['id']:<14}{rule['value']:.4g}  (needs {rule['operator']} {rule['threshold']})")
    for reason in summary.get("reasons", [])[:5] if summary["verdict"] in ("ERROR", "INCONCLUSIVE") else []:
        lines.append(f"  reason: {reason}")
    e = summary.get("explain")
    if e and e["status"] == "localised":
        lines.append(f"first difference: prompt {e['case_id']}, token step {e['first_token_difference']}")
        lines.append(f"  tensor {e['tensor']}, op {e['op']}, prompt position {e['position']}")
        if e.get("numeric"):
            n = e["numeric"]
            lines.append(f"  max abs error {n['max_absolute_error']:.2g}, max {n['max_ulp_error']} ULP")
        legality = e.get("legality")
        if isinstance(legality, dict):
            detail = legality.get("reason") or f"max ratio to the bound {legality.get('max_ratio', 0):.2g}"
            lines.append(f"  legality {legality['status']} ({detail})")
    elif e:
        lines.append(f"first difference: prompt {e['case_id']}, token step {e.get('first_token_difference')}")
        lines.append(f"  localisation {e['status']}: {e.get('reason')}")
    if summary.get("report"):
        lines.append(f"report: {summary['report']}")
    return "\n".join(lines)
