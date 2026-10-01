#!/usr/bin/env python3
"""Capture actual test/lint/build checks with timestamps and exit status."""

from pathlib import Path
import subprocess
import sys
from vfg.manifest import atomic_json, file_digest, now, digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/validation"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source_files = {
        p.relative_to(ROOT).as_posix(): file_digest(p)
        for directory in ("src", "scripts", "tests", "runner", "microbench")
        for p in sorted((ROOT / directory).rglob("*"))
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix in (".py", ".c", ".cpp", ".hpp", ".S", ".ld", ".txt")
    }
    for name in ("pyproject.toml", "uv.lock", "CMakeLists.txt", "CMakePresets.json"):
        source_files[name] = file_digest(ROOT / name)
    checks = [
        ("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"]),
        ("pytest", [sys.executable, "-m", "pytest", "tests", "-q", "--junitxml=" + str(OUT / "pytest.xml")]),
        ("host-configure", ["cmake", "--preset", "host-debug"]),
        ("host-build", ["cmake", "--build", "--preset", "host-debug"]),
        ("host-ctest", ["ctest", "--test-dir", "build/host-debug", "--output-on-failure"]),
    ]
    receipts = []
    for name, command in checks:
        start = now()
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        log = OUT / (name + ".log")
        log.write_text(result.stdout + result.stderr)
        receipt = {
            "name": name,
            "command": command,
            "started_at": start,
            "finished_at": now(),
            "returncode": result.returncode,
            "log": log.name,
            "log_sha256": file_digest(log),
        }
        if name == "pytest":
            receipt.update(junit="pytest.xml", junit_sha256=file_digest(OUT / "pytest.xml"))
        receipts.append(receipt)
        print(name, result.returncode, flush=True)
        if result.returncode:
            print((result.stdout + result.stderr)[-4000:])
    unchanged = all(file_digest(ROOT / name) == sha for name, sha in source_files.items())
    atomic_json(
        OUT / "receipt.json",
        {
            "schema_version": 1,
            "checks": receipts,
            "python": sys.version,
            "source_files": source_files,
            "source_sha256": digest(source_files),
            "source_unchanged_during_validation": unchanged,
        },
    )
    if not unchanged:
        raise RuntimeError("source changed during validation; receipt is not acceptable")
    return int(any(r["returncode"] for r in receipts))


if __name__ == "__main__":
    raise SystemExit(main())
