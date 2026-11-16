"""Print the first tensor that differs between two runner capture directories.

Usage: python first_diff.py <dir-a> <dir-b>
Each directory is the output of `vfg-llama-runner capture-c001-request.json <dir>`
(set model_path in the request first).
"""
import json
import sys

import numpy as np

a_dir, b_dir = sys.argv[1:3]
A = [json.loads(x) for x in open(f"{a_dir}/captures.jsonl")]
B = [json.loads(x) for x in open(f"{b_dir}/captures.jsonl")]
assert len(A) == len(B), "capture counts differ"
for a, b in zip(A, B):
    assert (a["name"], a["op"], a["position"]) == (b["name"], b["op"], b["position"]), "captures not aligned"
    if a["sha256"] != b["sha256"]:
        x = np.fromfile(f"{a_dir}/{a['payload']}", dtype="<f4")
        y = np.fromfile(f"{b_dir}/{b['payload']}", dtype="<f4")
        n = int(np.count_nonzero(x.view("<u4") != y.view("<u4")))
        print(f"first difference: position {a['position']}, tensor {a['name']}, op {a['op']}, "
              f"{n} of {x.size} values differ, max abs {np.max(np.abs(x - y)):.3g}")
        break
else:
    print("all captured tensors are bit-identical")
