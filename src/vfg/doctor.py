import os
from pathlib import Path
import platform
import shutil
import subprocess
from .manifest import now


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
    usage = shutil.disk_usage(Path.cwd())
    return {
        "schema_version": 1,
        "observed_at": now(),
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "disk_free_bytes": usage.free,
        "tools": tools,
        "affinity_supported": hasattr(os, "sched_setaffinity"),
        "physical_rvv_target": "not_probed",
        "limitations": ["No primary RVV board has been configured."],
    }
