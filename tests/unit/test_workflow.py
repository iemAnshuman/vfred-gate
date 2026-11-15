import json
import subprocess

import pytest

from vfg.errors import VFGError
from vfg.schema import Contract
from vfg.sources import local_checkout, resolve_ref
from vfg.workflow import PRESETS, differing_case, load_prompts, make_contract, model_lock


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_contract_presets_validate(preset):
    contract = make_contract(preset, 7, 3)
    assert Contract.model_validate(contract.model_dump()) == contract
    assert contract.evidence.minimum_cases == 7 and contract.evidence.repetitions == 3


def test_unknown_preset_rejected():
    with pytest.raises(VFGError, match="unknown contract preset"):
        make_contract("vibes", 4, 3)


def test_default_prompts_and_limits():
    rows = load_prompts(cases=5)
    assert [r["id"] for r in rows] == ["c001", "c002", "c003", "c004", "c005"]
    assert {r["split"] for r in rows} == {"exploratory"}
    assert len({r["group_id"] for r in rows}) == 5


def test_text_and_jsonl_prompts(tmp_path):
    text = tmp_path / "p.txt"
    text.write_text("first\n\n second \n")
    assert [r["text"] for r in load_prompts(text, None)] == ["first", " second "]
    jsonl = tmp_path / "p.jsonl"
    jsonl.write_text(json.dumps({"id": "x", "text": "hello"}) + "\n" + json.dumps({"text": "two"}) + "\n")
    assert [r["id"] for r in load_prompts(jsonl, None)] == ["x", "p002"]
    jsonl.write_text(json.dumps({"id": "x", "text": ""}) + "\n")
    with pytest.raises(VFGError, match="no text"):
        load_prompts(jsonl, None)
    empty = tmp_path / "e.txt"
    empty.write_text("\n")
    with pytest.raises(VFGError, match="no prompts"):
        load_prompts(empty, None)


def test_model_lock_requires_gguf(tmp_path):
    bad = tmp_path / "model-q4_0.gguf"
    bad.write_bytes(b"ABCD" + b"\0" * 10)
    with pytest.raises(VFGError, match="not a GGUF"):
        model_lock(bad)
    bad.write_bytes(b"GGUF" + b"\0" * 10)
    lock = model_lock(bad)
    assert lock.quantisation == "q4_0" and lock.size_bytes == 14 and lock.revision is None
    with pytest.raises(VFGError, match="not found"):
        model_lock(tmp_path / "missing.gguf")


def test_resolve_ref_validates_without_network():
    commit = "552f18f912a32ea86edf82e2b76431cb7131538d"
    assert resolve_ref(commit) == commit
    for bad in ("--upload-pack=x", "a b", "x" * 101, ""):
        with pytest.raises(VFGError, match="invalid"):
            resolve_ref(bad)


def _git(path, *args):
    subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)


def test_local_checkout_records_dirty_state(tmp_path):
    (tmp_path / "include").mkdir()
    (tmp_path / "include/llama.h").write_text("// header\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    _, clean = local_checkout(tmp_path)
    assert clean["kind"] == "local" and not clean["dirty"] and len(clean["commit"]) == 40
    (tmp_path / "include/llama.h").write_text("// changed\n")
    _, edited = local_checkout(tmp_path)
    assert edited["dirty"] and edited["diff_sha256"] != clean["diff_sha256"]
    (tmp_path / "include/llama.h").write_text("// header\n")
    (tmp_path / "new.c").write_text("int x;\n")
    _, untracked = local_checkout(tmp_path)
    assert untracked["dirty"] and untracked["untracked_sha256"] != clean["untracked_sha256"]
    nested = tmp_path / "sub"
    (nested / "include").mkdir(parents=True)
    (nested / "include/llama.h").write_text("// nested\n")
    with pytest.raises(VFGError, match="root of its git checkout"):
        local_checkout(nested)


def test_local_checkout_rejects_non_llama(tmp_path):
    with pytest.raises(VFGError, match="not a llama.cpp source tree"):
        local_checkout(tmp_path)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_differing_case_prefers_token_divergence_then_bits(tmp_path):
    rules = [{"first_divergences": [{"case_id": "a", "position": None}, {"case_id": "b", "position": 3}]}]
    _write(tmp_path / "verdict.json", {"rules": rules})
    _write(tmp_path / "run.json", {"jobs": []})
    assert differing_case(tmp_path) == "b"
    _write(tmp_path / "verdict.json", {"rules": [{"first_divergences": [{"case_id": "a", "position": None}]}]})
    jobs = []
    for case, (left, right) in {"a": ("1", "1"), "c": ("2", "3")}.items():
        for role, sha in (("baseline", left), ("candidate", right)):
            path = f"jobs/{case}/{role}"
            jobs.append({"case_id": case, "role": role, "mode": "free_run", "repetition": 0, "path": path})
            _write(tmp_path / path / "output/result.json", {"logits_sha256": sha})
    _write(tmp_path / "run.json", {"jobs": jobs})
    assert differing_case(tmp_path) == "c"
