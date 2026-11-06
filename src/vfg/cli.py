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
app.add_typer(corpus_app, name="corpus")


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


@app.command()
def doctor(output: Optional[Path] = typer.Option(None)):
    from .doctor import doctor as inventory

    data = guarded(inventory)
    if output:
        atomic_json(output, data)
    typer.echo(json.dumps(data, indent=2))


@app.command()
def validate(plan: Path = typer.Option(...)):
    from .controller import resolve_plan

    resolved = guarded(resolve_plan, plan)
    typer.echo(f"valid: {resolved.plan.id} / {len(resolved.cases)} cases")


@app.command()
def build(
    stack: Path = typer.Option(Path("stacks/baseline.json")),
    build_dir: Path = typer.Option(Path("build/host-release")),
    compiler: Optional[Path] = typer.Option(None),
    extra_flags: Optional[str] = typer.Option(None),
):
    import shlex
    from .build import build_native

    data = guarded(
        build_native,
        build_dir,
        stack,
        compiler=compiler,
        extra_flags=shlex.split(extra_flags) if extra_flags else None,
    )
    typer.echo(json.dumps({"binary_sha256": data["binary_sha256"], "stack": str(stack)}))


@app.command()
def scan(binary: Path = typer.Option(...), output: Path = typer.Option(...)):
    from .scan.elf import scan_binary

    data = guarded(scan_binary, binary, output)
    atomic_json(output, data)
    typer.echo(json.dumps(data, indent=2))


@app.command()
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


@app.command()
def qualify(plan: Path = typer.Option(...), output: Path = typer.Option(...)):
    from .controller import qualify as run

    verdict = guarded(run, plan, output, lambda message: typer.echo(message, err=True))
    typer.echo(verdict.model_dump_json(indent=2))
    raise typer.Exit(verdict.exit_code)


@app.command()
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


@app.command()
def report(
    run: Path = typer.Option(...),
    output: Path = typer.Option(...),
    offline: bool = typer.Option(False),
    localisation: Optional[Path] = typer.Option(None),
    inventory: Optional[Path] = typer.Option(None),
):
    from .report import render_report

    typer.echo(str(guarded(render_report, run, output, localisation, inventory)))


@app.command()
def localise(
    qualification: Path = typer.Option(...),
    case: str = typer.Option(...),
    capture: str = typer.Option("layer"),
    output: Optional[Path] = typer.Option(None),
):
    from .replay import localise as replay

    result = guarded(replay, qualification, case, capture, output)
    typer.echo(json.dumps(result, indent=2))


@app.command()
def canary(
    exploratory: Path = typer.Option(...),
    holdout: Path = typer.Option(...),
    output: Optional[Path] = typer.Option(None),
):
    from .canary.study import run_study

    result = guarded(run_study, exploratory, holdout, output)
    typer.echo(json.dumps(result["selection"], indent=2))


@app.command()
def progress(ledger: Path = typer.Option(Path("docs/progress.yaml"))):
    from .progress import check_progress

    result = guarded(check_progress, ledger)
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
