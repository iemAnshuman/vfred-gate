#!/usr/bin/env python3
"""Compiler launcher that applies candidate flags except to named strict sources.

CMake invokes this as: flag_filter.py CONFIG COMPILER [ARGS...]
"""

import json
import subprocess
import sys


def main():
    if len(sys.argv) < 3:
        print("usage: flag_filter.py CONFIG COMPILER [ARGS...]", file=sys.stderr)
        return 2
    config = json.loads(open(sys.argv[1]).read())
    command = sys.argv[2:]
    if "-c" in command:
        source = command[command.index("-c") + 1]
        strict = any(source.endswith(suffix) for suffix in config.get("strict_sources", []))
        flags = config.get("strict_flags" if strict else "candidate_flags", [])
        command = command + flags
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
