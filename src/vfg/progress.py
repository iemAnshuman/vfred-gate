"""Acceptance credits require checked evidence; proposed work earns no points."""

from pathlib import Path
import xml.etree.ElementTree as ET
from .errors import VFGError
from .manifest import file_digest, load_document, resolve
from .controller import rederive
from .replay.localise import verify_localisation
from .store import verify_bundle

WEIGHTS = {
    "W0.host": 2,
    "W0.compile": 2,
    "W0.emulator": 2,
    "W0.board": 4,
    "W1.schemas": 3,
    "W1.artifacts": 3,
    "W1.build": 3,
    "W1.execute": 3,
    "W2.scan": 6,
    "W3.native": 7,
    "W3.rvv": 3,
    "W4.metrics": 4,
    "W4.verdicts": 3,
    "W4.end_to_end": 3,
    "W5.replay": 2,
    "W5.capture": 2,
    "W5.seeded": 2,
    "W5.mechanism": 4,
    "W5.model": 8,
    "W6.pilot": 2,
    "W6.prediction": 6,
    "W7.replay": 8,
    "W7.independent": 4,
    "W8.search": 6,
    "W8.cost": 4,
    "W9.docs": 2,
    "W9.study": 2,
}


def check_progress(ledger):
    ledger = Path(ledger).resolve()
    data = load_document(ledger)
    items = data["items"]
    if len({x["id"] for x in items}) != len(items):
        raise VFGError("duplicate credit ID")
    if {x["id"]: x["weight"] for x in items} != WEIGHTS or sum(x["weight"] for x in items) != 100:
        raise VFGError("weights differ from agreed 100-point rubric")
    accepted = 0
    blocked = []
    claims = set()
    checked = []
    for item in items:
        if item["status"] in ("blocked", "deferred"):
            blocked.append({"id": item["id"], "weight": item["weight"], "reason": item["reason"]})
            continue
        if item["status"] != "accepted" or not item.get("evidence"):
            raise VFGError("accepted item needs evidence")
        for evidence in item["evidence"]:
            claim = evidence["claim"]
            if claim in claims:
                raise VFGError("duplicate evidence credit")
            claims.add(claim)
            path = resolve(ledger.parent, evidence["path"])
            if file_digest(path) != evidence["sha256"]:
                raise VFGError(f"evidence changed: {path}")
            kind = evidence["kind"]
            if kind == "pytest":
                tree = ET.parse(path)
                cases = tree.findall(".//testcase")
                if not cases or any(
                    c.find("failure") is not None
                    or c.find("error") is not None
                    or c.find("skipped") is not None
                    for c in cases
                ):
                    raise VFGError("tests failed or skipped; points cannot be earned")
                observed = {c.get("classname") + "." + c.get("name") for c in cases}
                if not set(evidence["tests"]) <= observed:
                    raise VFGError("acceptance tests were not run")
            elif kind == "qualification":
                result = rederive(path.parent)["verdict"]
                if (
                    result["verdict"] != evidence["verdict"]
                    or result["evidence"]["distinct_cases"] < evidence["minimum_cases"]
                ):
                    raise VFGError("qualification acceptance mismatch")
            elif kind == "localisation":
                result = verify_localisation(path.parent)
                if (
                    not result["baseline_restored"]
                    or not result["history_matched"]
                    or not result["original_discrepancy_preserved"]
                ):
                    raise VFGError("replay acceptance failed")
                if result["earliest_difference"]["name"] != "l_out-0" or not result["injected_diagnostic"]:
                    raise VFGError("seeded site was not located")
            elif kind == "bundle":
                verify_bundle(path.parent, evidence["sha256"])
            elif kind == "file":
                pass
            else:
                raise VFGError("unknown evidence kind")
        accepted += item["weight"]
        checked.append(item["id"])
    return {
        "rubric_points": 100,
        "accepted_points": accepted,
        "unearned_points": 100 - accepted,
        "accepted_items": checked,
        "blocked_or_deferred": blocked,
        "scope": "host/emulator software milestone; physical-board and full-model RVV qualification pending",
    }
