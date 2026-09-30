#!/usr/bin/env python3
import argparse
import json
from vfg.progress import check_progress
from vfg.errors import VFGError

p = argparse.ArgumentParser()
p.add_argument("--ledger", default="docs/progress.yaml")
p.add_argument("--min-points", type=int, default=50)
a = p.parse_args()
try:
    result = check_progress(a.ledger)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["accepted_points"] >= a.min_points else 3)
except (VFGError, OSError, ValueError, KeyError) as exc:
    print(json.dumps({"verdict": "ERROR", "reason": str(exc)}))
    raise SystemExit(4)
