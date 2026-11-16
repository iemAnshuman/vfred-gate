"""Local-only CLI. No command publishes evidence or pushes Git history."""

from pathlib import Path
from typing import Optional
import json
import subprocess
import sys
import typer
from .errors import VFGError, InsufficientEvidence
from .manifest import atomic_json, load_document

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
corpus_app = typer.Typer(no_args_is_help=True)
app.add_typer(corpus_app, name="corpus", rich_help_panel="Research record", help="Manage the research prompt corpus.")


def _version(value: bool):
    if value:
        from . import __version__

        typer.echo(f"vfg {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show the version and exit."),
):
    """Numerical compatibility gate for llama.cpp builds: verdict, first differing op, offline evidence."""


def fail(exc):
    typer.echo(json.dumps({"verdict": "ERROR", "exit_code": 4, "reason": str(exc)}), err=True)
    raise typer.Exit(4)


def guarded(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except InsufficientEvidence as exc:
        typer.echo(json.dumps({"verdict": "INCONCLUSIVE", "exit_code": 3, "reason": str(exc)}), err=True)
        raise typer.Exit(3)
    except (VFGError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        fail(exc)


@app.command(rich_help_panel="Main", help="Check that the build tools (CMake, Ninja, a C/C++ compiler) are available.")
def doctor(output: Optional[Path] = typer.Option(None)):
    from .doctor import doctor as inventory

    data = guarded(inventory)
    if output:
        atomic_json(output, data)
    typer.echo(json.dumps(data, indent=2))


@app.command(rich_help_panel="Research record", help="Validate a research plan file.")
def validate(plan: Path = typer.Option(...)):
    from .controller import resolve_plan

    resolved = guarded(resolve_plan, plan)
    typer.echo(f"valid: {resolved.plan.id} / {len(resolved.cases)} cases")


@app.command(rich_help_panel="Research record", help="Build one stack of a research plan.")
def build(
    stack: Path = typer.Option(Path("stacks/baseline.json")),
    build_dir: Path = typer.Option(Path("build/host-release")),
    compiler: Optional[Path] = typer.Option(None),
    extra_flags: Optional[str] = typer.Option(None),
    candidate_flags: Optional[str] = typer.Option(None),
    strict_sources: Optional[str] = typer.Option(None),
    reduction_policy: str = typer.Option("native"),
):
    import shlex
    from .build import build_native

    data = guarded(
        build_native,
        build_dir,
        stack,
        compiler=compiler,
        extra_flags=shlex.split(extra_flags) if extra_flags else None,
        candidate_flags=shlex.split(candidate_flags) if candidate_flags else None,
        strict_sources=[x for x in (strict_sources or "").split(",") if x],
        reduction_policy=reduction_policy,
    )
    typer.echo(json.dumps({"binary_sha256": data["binary_sha256"], "stack": str(stack)}))


@app.command(rich_help_panel="Research record", help="List the RVV reduction instructions in a binary.")
def scan(binary: Path = typer.Option(...), output: Path = typer.Option(...)):
    from .scan.elf import scan_binary

    data = guarded(scan_binary, binary, output)
    atomic_json(output, data)
    typer.echo(json.dumps(data, indent=2))


@app.command(rich_help_panel="Research record", help="Run the reduction microbenchmark.")
def microbench(
    output: Path = typer.Option(Path("runs/mechanism")), target: Optional[Path] = typer.Option(None)
):
    if target:
        from .schema import Target

        t = guarded(load_document, target, Target)
        if t.execution_class != "emulator" or t.architecture != "rv64":
            fail("this command implements the RVV QEMU probe target")
    script = Path(__file__).resolve().parents[2] / "scripts/rvv_probe.py"
    guarded(subprocess.run, [sys.executable, str(script), "--output", str(output)], check=True)


@corpus_app.command("freeze")
def freeze(
    source: Path = typer.Option(...),
    model: Path = typer.Option(...),
    binary: Path = typer.Option(Path("build/host-release/runner/vfg-llama-runner")),
    output: Path = typer.Option(Path("corpora/pilot-v1.jsonl")),
):
    from .canary.corpus import freeze_corpus

    data = guarded(freeze_corpus, source, model, binary, output)
    typer.echo(json.dumps(data, indent=2))


@app.command(rich_help_panel="Research record", help="Run a research qualification plan.")
def qualify(plan: Path = typer.Option(...), output: Path = typer.Option(...)):
    from .controller import qualify as run

    verdict = guarded(run, plan, output, lambda message: typer.echo(message, err=True))
    typer.echo(verdict.model_dump_json(indent=2))
    raise typer.Exit(verdict.exit_code)


@app.command(rich_help_panel="Main", help="Recompute the verdict of an evidence bundle offline and check its hashes.")
def verify(run: Path = typer.Option(...)):
    from .controller import rederive

    result = guarded(rederive, run)
    typer.echo(
        json.dumps(
            {
                "verified": True,
                "verdict": result["verdict"]["verdict"],
                "bundle_sha256": result["bundle_sha256"],
            }
        )
    )


@app.command(rich_help_panel="Research record", help="Write the HTML report of a run.")
def report(
    run: Path = typer.Option(...),
    output: Path = typer.Option(...),
    offline: bool = typer.Option(False),
    localisation: Optional[Path] = typer.Option(None),
    inventory: Optional[Path] = typer.Option(None),
):
    from .report import render_report

    typer.echo(str(guarded(render_report, run, output, localisation, inventory)))


@app.command(rich_help_panel="Research record", help="Localise a difference in a research qualification.")
def localise(
    qualification: Path = typer.Option(...),
    case: str = typer.Option(...),
    capture: str = typer.Option("layer"),
    output: Optional[Path] = typer.Option(None),
):
    from .replay import localise as replay

    result = guarded(replay, qualification, case, capture, output)
    typer.echo(json.dumps(result, indent=2))


@app.command(rich_help_panel="Research record", help="Run the canary prompt study.")
def canary(
    exploratory: Path = typer.Option(...),
    holdout: Path = typer.Option(...),
    output: Optional[Path] = typer.Option(None),
):
    from .canary.study import run_study

    result = guarded(run_study, exploratory, holdout, output)
    typer.echo(json.dumps(result["selection"], indent=2))


def _which(compiler):
    import shutil

    if compiler is None:
        return None
    found = shutil.which(str(compiler))
    if found is None:
        fail(f"compiler not found: {compiler}")
    return Path(found)


def _split(value):
    import shlex

    return shlex.split(value) if value else []


@app.command(rich_help_panel="Main")
def compare(
    model: Path = typer.Option(..., help="GGUF model file."),
    a: str = typer.Option("pinned", help="Baseline: pinned, llama.cpp@<tag|commit>, or a local checkout."),
    b: str = typer.Option("pinned", help="Candidate: pinned, llama.cpp@<tag|commit>, or a local checkout."),
    a_cmake: Optional[str] = typer.Option(None, help='Baseline CMake options, e.g. "-DGGML_AVX512=ON".'),
    b_cmake: Optional[str] = typer.Option(None, help="Candidate CMake options."),
    a_cflags: Optional[str] = typer.Option(None, help='Baseline compiler flags, e.g. "-ffp-contract=fast".'),
    b_cflags: Optional[str] = typer.Option(None, help="Candidate compiler flags."),
    a_compiler: Optional[Path] = typer.Option(None, help="Baseline C++ compiler, e.g. g++-14 or clang++."),
    b_compiler: Optional[Path] = typer.Option(None, help="Candidate C++ compiler."),
    contract: str = typer.Option("decision", help="bit, decision or sequence."),
    prompts: Optional[Path] = typer.Option(None, help="Text file (one prompt per line) or JSONL with text."),
    cases: int = typer.Option(16, min=1, help="Number of prompts to use."),
    repetitions: int = typer.Option(3, min=2, help="Runs per prompt and build."),
    max_tokens: int = typer.Option(32, min=1, max=1024),
    context: int = typer.Option(512, min=16, max=65536, help="Context size; prompt plus output must fit."),
    output: Optional[Path] = typer.Option(None, help="New, empty run directory."),
    explain: bool = typer.Option(True, help="Localise the first difference after a FAIL."),
):
    """Compare two llama.cpp builds on one model: verdict, first difference, report."""
    from .workflow import compare as run

    summary = guarded(
        run,
        model,
        a,
        b,
        output,
        _split(a_cmake),
        _split(b_cmake),
        _split(a_cflags),
        _split(b_cflags),
        contract,
        prompts,
        cases,
        repetitions,
        max_tokens,
        context,
        run_explain=explain,
        progress=lambda message: typer.echo(message, err=True),
        a_compiler=_which(a_compiler),
        b_compiler=_which(b_compiler),
    )
    from .workflow import format_summary

    typer.echo(format_summary(summary), err=True)
    typer.echo(json.dumps(summary, indent=2))
    raise typer.Exit(summary["exit_code"])


@app.command(rich_help_panel="Main")
def explain(
    run: Path = typer.Option(..., help="Qualification bundle with a FAIL verdict."),
    output: Path = typer.Option(..., help="New directory for the localisation bundle."),
):
    """Localise the first observed difference of a qualification to a layer and ggml op."""
    from .workflow import explain as run_explain

    result = guarded(run_explain, run, output, lambda message: typer.echo(message, err=True))
    typer.echo(json.dumps(result, indent=2))


@app.command(rich_help_panel="Main")
def record(
    model: Path = typer.Option(..., help="GGUF model file."),
    a: str = typer.Option("pinned", help="Build to record: pinned, llama.cpp@<tag|commit>, or a local checkout."),
    a_cmake: Optional[str] = typer.Option(None, help="Extra CMake options."),
    a_cflags: Optional[str] = typer.Option(None, help="Extra compiler flags."),
    prompts: Optional[Path] = typer.Option(None, help="Text file (one prompt per line) or JSONL with text."),
    cases: int = typer.Option(16, min=1),
    repetitions: int = typer.Option(3, min=2),
    max_tokens: int = typer.Option(32, min=1, max=1024),
    context: int = typer.Option(512, min=16, max=65536, help="Context size; prompt plus output must fit."),
    output: Path = typer.Option(Path("runs/reference"), help="New, empty directory for the reference bundle."),
):
    """Record a portable reference on this machine, for `vfg check` on another machine."""
    from .reference import record as run

    result = guarded(
        run, model, a, output, _split(a_cmake), _split(a_cflags), prompts, cases, repetitions, max_tokens, context,
        progress=lambda message: typer.echo(message, err=True),
    )
    typer.echo(json.dumps(result, indent=2))


@app.command(rich_help_panel="Main")
def check(
    reference: Path = typer.Option(..., help="Reference bundle from `vfg record`."),
    model: Path = typer.Option(..., help="The same GGUF model file (checked by hash)."),
    b: str = typer.Option("pinned", help="Build to check: pinned, llama.cpp@<tag|commit>, or a local checkout."),
    b_cmake: Optional[str] = typer.Option(None, help="Extra CMake options."),
    b_cflags: Optional[str] = typer.Option(None, help="Extra compiler flags."),
    contract: str = typer.Option("decision", help="bit, decision or sequence."),
    output: Path = typer.Option(Path("runs/check"), help="New, empty directory for the qualification bundle."),
    reference_sha256: Optional[str] = typer.Option(None, help="Expected SHA-256 of the reference bundle.json."),
):
    """Check a build on this machine against a reference recorded elsewhere."""
    from .reference import check as run

    result = guarded(
        run, reference, model, b, output, _split(b_cmake), _split(b_cflags), contract,
        progress=lambda message: typer.echo(message, err=True),
        reference_sha256=reference_sha256,
    )
    typer.echo(json.dumps(result, indent=2))
    raise typer.Exit(result["exit_code"])


@app.command("fetch-model", rich_help_panel="Main")
def fetch_model(output: Optional[Path] = typer.Option(None, help="Directory for the model file.")):
    """Download the pinned demo model (SmolLM2-360M-Instruct Q8_0, 386 MB) and check its hash."""
    from .models import fetch_pinned

    typer.echo(str(guarded(fetch_pinned, output)))


@app.command(rich_help_panel="Research record", help="Check the research ledger.")
def progress(ledger: Path = typer.Option(Path("docs/progress.yaml"))):
    from .progress import check_progress

    result = guarded(check_progress, ledger)
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
