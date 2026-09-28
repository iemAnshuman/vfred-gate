#!/usr/bin/env python3
"""Explain native Mach-O build differences without asserting byte reproducibility."""

import argparse
from pathlib import Path
import struct
import subprocess
from vfg.manifest import atomic_json, file_digest, now


def sections(path):
    data = Path(path).read_bytes()
    if data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("requires little-endian 64-bit Mach-O")
    count = struct.unpack_from("<I", data, 16)[0]
    offset = 32
    result = {}
    for _ in range(count):
        command, size = struct.unpack_from("<II", data, offset)
        if command == 0x19:
            segment = data[offset + 8 : offset + 24].split(b"\0")[0].decode()
            n = struct.unpack_from("<I", data, offset + 64)[0]
            for i in range(n):
                p = offset + 72 + i * 80
                name = data[p : p + 16].split(b"\0")[0].decode()
                length, start = struct.unpack_from("<QI", data, p + 40)
                if start:
                    result[segment + "," + name] = data[start : start + length]
        offset += size
    return result


def compare(left, right, output):
    a = sections(left)
    b = sections(right)
    result = {
        "schema_version": 1,
        "checked_at": now(),
        "left": str(Path(left).resolve()),
        "right": str(Path(right).resolve()),
        "left_sha256": file_digest(left),
        "right_sha256": file_digest(right),
        "byte_identical": file_digest(left) == file_digest(right),
        "sections": {k: {"size_bytes": len(a[k]), "equal": a[k] == b.get(k)} for k in a},
        "section_sets_match": set(a) == set(b),
        "debug_object_symbols": {
            label: [
                s
                for s in subprocess.check_output(["nm", "-ap", str(p)], text=True).splitlines()
                if " OSO " in s
            ]
            for label, p in [("left", left), ("right", right)]
        },
        "limitation": "Mach-O debug object paths and object timestamps differ; UUID/signature/link-edit metadata can consequently differ. Full binary byte reproducibility is not claimed.",
    }
    atomic_json(output, result)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("left")
    p.add_argument("right")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    r = compare(a.left, a.right, a.output)
    print(
        "byte_identical=",
        r["byte_identical"],
        "all_loadable_sections_equal=",
        all(x["equal"] for x in r["sections"].values()),
    )
