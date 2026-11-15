import os
from pathlib import Path
import platform
import shutil
import subprocess
from .manifest import now


def _ninja():
    from .build import find_tool

    try:
        return find_tool("ninja")
    except Exception:
        return None


def doctor():
    tools = {}
    for name in (
        "python3",
        "uv",
        "cmake",
        "ninja",
        "clang",
        "clang++",
        "llvm-objdump",
        "llvm-readelf",
        "ld.lld",
        "qemu-system-riscv64",
    ):
        path = shutil.which(name)
        if path is None and name == "ld.lld":
            fallback = Path("/opt/homebrew/opt/lld/bin/ld.lld")
            if fallback.exists():
                path = str(fallback)
        item = {"status": "missing", "path": None}
        if path:
            p = subprocess.run([path, "--version"], text=True, capture_output=True, timeout=10)
            item = {"status": "available", "path": path, "version": (p.stdout or p.stderr).splitlines()[0]}
        tools[name] = item
    required = {
        "cmake": shutil.which("cmake"),
        "ninja": _ninja(),
        "c++ compiler": shutil.which("c++") or shutil.which("clang++") or shutil.which("g++"),
        "git": shutil.which("git"),
    }
    missing = [name for name, path in required.items() if path is None]
    hint = (
        "brew install cmake ninja"
        if platform.system() == "Darwin"
        else "sudo apt-get install cmake ninja-build g++ git"
    )
    usage = shutil.disk_usage(Path.cwd())
    return {
        "schema_version": 1,
        "observed_at": now(),
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "disk_free_bytes": usage.free,
        "tools": tools,
        "compare_ready": not missing,
        "compare_missing": missing,
        "install_hint": hint if missing else None,
        "affinity_supported": hasattr(os, "sched_setaffinity"),
        "physical_rvv_target": "not_probed",
        "limitations": ["No primary RVV board has been configured."],
    }
