#!/usr/bin/env python3
"""Search for a reproducible ordered/unordered RVV reduction difference in QEMU."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from vfg.scan.elf import scan_binary

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
    ap.add_argument("--output", type=Path, default=ROOT / "runs/mechanism-search")
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("search output is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)

    clang = tool("clang", "/opt/homebrew/opt/llvm/bin/clang")
    if Path("/opt/homebrew/opt/llvm/bin/clang").exists():
        clang = "/opt/homebrew/opt/llvm/bin/clang"
    lld = tool("ld.lld", "/opt/homebrew/opt/lld/bin/ld.lld")
    objdump = tool("llvm-objdump", "/opt/homebrew/opt/llvm/bin/llvm-objdump")
    qemu = tool("qemu-system-riscv64", "/opt/homebrew/bin/qemu-system-riscv64")

    elf = out / "search.elf"
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
        str(ROOT / "microbench/rvv/search.c"),
        "-o",
        str(elf),
    ]
    built = subprocess.run(command, text=True, capture_output=True)
    (out / "build.log").write_text(built.stdout + built.stderr)
    built.check_returncode()

    dis = subprocess.check_output([objdump, "-d", "-l", str(elf)], text=True)
    (out / "disassembly.txt").write_text(dis)

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
    result = subprocess.run(run, text=True, capture_output=True, timeout=180)
    (out / "stdout.json").write_text(result.stdout)
    (out / "stderr.txt").write_text(result.stderr)
    if result.returncode not in (0, 2):
        raise RuntimeError(result.stderr[-2000:])
    data = json.loads(result.stdout)
    if data["found"]:
        if not data["ordered_matches_scalar"]:
            raise RuntimeError("ordered reduction does not match the scalar left fold")
        if data["ordered_bits"] == data["unordered_bits"]:
            raise RuntimeError("recorded policies do not differ")

    inventory = scan_binary(elf, out / "inventory.json", objdump=objdump)
    policy_sites = {}
    for site in inventory["sites"]:
        policy_sites.setdefault(site["mnemonic"], []).append(
            {
                "site_id": site["site_id"],
                "symbols": site["symbols"],
                "source_candidates": site["source_candidates"],
            }
        )
    if "vfredosum.vs" not in policy_sites or "vfredusum.vs" not in policy_sites:
        raise RuntimeError("the ELF does not contain both reduction policies")

    manifest = {
        "schema_version": 1,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "execution_class": "emulator",
        "build_command": command,
        "execution_command": run,
        "compiler_version": subprocess.check_output([clang, "--version"], text=True),
        "qemu_version": subprocess.check_output([qemu, "--version"], text=True),
        "binary_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256((ROOT / "microbench/rvv/search.c").read_bytes()).hexdigest(),
        "search": data["search"],
        "found": data["found"],
        "found_trial": data["found_trial"],
        "n": data["n"],
        "ordered_bits": data["ordered_bits"],
        "unordered_bits": data["unordered_bits"],
        "scalar_bits": data["scalar_bits"],
        "ordered_fflags": data["ordered_fflags"],
        "unordered_fflags": data["unordered_fflags"],
        "ordered_matches_scalar": data["ordered_matches_scalar"],
        "dynamic": data["dynamic"],
        "samples": len(data.get("samples", [])),
        "static_sites": policy_sites,
        "toggle": {
            "policy_a": "vfredosum.vs",
            "policy_b": "vfredusum.vs",
            "same_input": True,
            "output_changed": bool(data["found"]),
            "ordered_restored_by_repeat": bool(data["found"]),
        },
        "physical_board_gate": "blocked",
        "scope": "freestanding RVV 1.0 probe; not a model-level attribution",
        "conclusion": (
            "reproducible ordered/unordered difference observed"
            if data["found"]
            else "bounded negative: QEMU returned identical ordered and unordered results for every trial"
        ),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "trials": manifest["search"]["trials"],
                "n": manifest["n"],
                "ordered_bits": manifest["ordered_bits"],
                "unordered_bits": manifest["unordered_bits"],
                "dynamic": manifest["dynamic"],
            }
        )
    )


if __name__ == "__main__":
    main()
