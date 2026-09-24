#!/usr/bin/env python3
from pathlib import Path
import json
from vfg.schema import SCHEMAS

out = Path(__file__).resolve().parents[1] / "schemas"
out.mkdir(exist_ok=True)
for name, model in SCHEMAS.items():
    (out / f"{name}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
print(f"Exported {len(SCHEMAS)} schemas")
