"""Bounded subprocess execution with recorded inputs and no shell interpolation."""

import os
from pathlib import Path
import platform
import signal
import subprocess
import time
from ..errors import VFGError, InsufficientEvidence
from ..manifest import atomic_json, file_digest, now


def execute_command(command, output, timeout=120, cwd=None, affinity_cpu=None, require_affinity=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    environment = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TMPDIR") if k in os.environ}
    environment.update({"LC_ALL": "C", "LANG": "C", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
    affinity = {"requested": affinity_cpu, "applied": False, "supported": hasattr(os, "sched_setaffinity")}
    before = None
    if affinity_cpu is not None:
        if hasattr(os, "sched_setaffinity"):
            if affinity_cpu not in os.sched_getaffinity(0):
                raise InsufficientEvidence("requested CPU is outside the allowed affinity set")

            def before():
                os.sched_setaffinity(0, {affinity_cpu})

            affinity["applied"] = True
        elif require_affinity:
            raise InsufficientEvidence("required CPU affinity is unavailable")
    start = now()
    clock = time.monotonic()
    status = "complete"
    code = None
    try:
        with (output / "stdout.txt").open("wb") as stdout, (output / "stderr.txt").open("wb") as stderr:
            proc = subprocess.Popen(
                [str(x) for x in command],
                cwd=cwd,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                preexec_fn=before,
            )
            try:
                code = proc.wait(timeout=timeout)
                if code:
                    status = "error"
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                status = "timeout"
    except OSError as exc:
        raise VFGError(f"cannot execute {command[0]}: {exc}") from exc
    result = {
        "command": [str(x) for x in command],
        "cwd": str(Path(cwd or Path.cwd()).resolve()),
        "started_at": start,
        "finished_at": now(),
        "elapsed_seconds": time.monotonic() - clock,
        "returncode": code,
        "status": status,
        "affinity": affinity,
        "os": platform.platform(),
        "environment": environment,
    }
    atomic_json(output / "execution.json", result)
    return result


def execute_runner(binary, request, output, target, timeout=120):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise VFGError("runner output directory is not empty")
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "request.json", request)
    command = [
        *target.command_prefix,
        str(Path(binary).resolve()),
        str((output / "request.json").resolve()),
        str((output / "output").resolve()),
    ]
    execution = execute_command(
        command, output, timeout, affinity_cpu=target.affinity_cpu, require_affinity=target.require_affinity
    )
    execution["execution_class"] = target.execution_class
    execution["binary_sha256"] = file_digest(binary)
    atomic_json(output / "execution.json", execution)
    return execution
