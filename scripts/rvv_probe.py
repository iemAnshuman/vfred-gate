#!/usr/bin/env python3
"""Build and execute a freestanding RVV 1.0 probe without a Linux sysroot."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def tool(name, fallback):
    found = shutil.which(name)
    if found:
        return found
    if Path(fallback).is_file():
        return fallback
    raise RuntimeError(f"missing {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ROOT / "runs/mechanism")
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("probe output is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)
    clang = tool("clang", "/opt/homebrew/opt/llvm/bin/clang")
    if Path("/opt/homebrew/opt/llvm/bin/clang").exists():
        clang = "/opt/homebrew/opt/llvm/bin/clang"
    lld = tool("ld.lld", "/opt/homebrew/opt/lld/bin/ld.lld")
    objdump = tool("llvm-objdump", "/opt/homebrew/opt/llvm/bin/llvm-objdump")
    qemu = tool("qemu-system-riscv64", "/opt/homebrew/bin/qemu-system-riscv64")
    elf = out / "probe.elf"
    command = [
        clang,
        "--target=riscv64-unknown-elf",
        "-march=rv64gcv",
        "-mabi=lp64d",
        "-mcmodel=medany",
        "-O2",
        "-g",
        "-fno-fast-math",
        "-ffp-contract=off",
        "-fno-vectorize",
        "-fno-slp-vectorize",
        "-ffreestanding",
        "-nostdlib",
        "-fno-stack-protector",
        f"-fuse-ld={lld}",
        "-Wl,--no-relax",
        "-Wl,-T," + str(ROOT / "microbench/rvv/link.ld"),
        str(ROOT / "microbench/rvv/start.S"),
        str(ROOT / "microbench/rvv/probe.c"),
        "-o",
        str(elf),
    ]
    built = subprocess.run(command, text=True, capture_output=True)
    (out / "build.log").write_text(built.stdout + built.stderr)
    built.check_returncode()
    dis = subprocess.check_output([objdump, "-d", "-l", str(elf)], text=True)
    (out / "disassembly.txt").write_text(dis)
    assert "vfredosum.vs" in dis and "vfredusum.vs" in dis
    run = [
        qemu,
        "-machine",
        "virt",
        "-cpu",
        "rv64,v=true,vlen=256,elen=64",
        "-m",
        "128M",
        "-smp",
        "1",
        "-bios",
        "none",
        "-nographic",
        "-monitor",
        "none",
        "-kernel",
        str(elf),
    ]
    result = subprocess.run(run, text=True, capture_output=True, timeout=30)
    (out / "stdout.json").write_text(result.stdout)
    (out / "stderr.txt").write_text(result.stderr)
    result.check_returncode()
    data = json.loads(result.stdout)
    assert data["ordered_matches_scalar"]
    groups = {}
    for row in data["records"]:
        key = (row["fixture"], row["n"])
        groups.setdefault(key, set()).add((row["ordered_bits"], row["unordered_bits"]))
    assert all(len(v) == 1 for v in groups.values())
    manifest = {
        "schema_version": 1,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "execution_class": "emulator",
        "build_command": command,
        "execution_command": run,
        "compiler_version": subprocess.check_output([clang, "--version"], text=True),
        "qemu_version": subprocess.check_output([qemu, "--version"], text=True),
        "binary_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
        "sources": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "microbench/rvv").glob("*"))
        },
        "records": len(data["records"]),
        "distinct_cases": len(groups),
        "policy_differences": sum(r["ordered_bits"] != r["unordered_bits"] for r in data["records"]),
        "physical_board_gate": "blocked",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in ("records", "distinct_cases", "policy_differences", "physical_board_gate")
            }
        )
    )


if __name__ == "__main__":
    main()
