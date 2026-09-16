import json
import pytest
from vfg.manifest import canonical, digest, diff_manifests, load_document
from vfg.errors import VFGError
from vfg.schema import Contract, Verdict

def test_canonical_and_changes():
    assert canonical({"b":2,"a":1})==canonical({"a":1,"b":2})
    assert digest({"a":1})!=digest({"a":2})
    result=diff_manifests({"id":"a","compiler":"gcc","model":"one"},{"id":"b","compiler":"clang","model":"two"},["compiler"])
    assert set(result["planned"])=={"compiler"}
    assert set(result["uncontrolled"])=={"model"}

@pytest.mark.parametrize("suffix,body",[
    (".yaml","id: one\nid: two"),(".json",'{"id":1,"id":2}'),
    (".json",'{"a":NaN}'),(".yaml","a: .nan"),
    (".yaml","!!python/object/apply:os.system ['echo unsafe']")])
def test_reject_ambiguous_document(tmp_path,suffix,body):
    p=tmp_path/("input"+suffix);p.write_text(body)
    with pytest.raises(VFGError): load_document(p)

def test_strict_contract(tmp_path):
    d={"id":"test","compatibility_level":"decision","rules":[
        {"id":"a","metric":"argmax_agreement_rate","operator":"ge","threshold":1.0}]}
    assert Contract.model_validate(d).evidence.repetitions==5
    for changes in [{"unexpected":1},{"compatibility_level":"task"},
                    {"rules":[dict(d["rules"][0],threshold=float("nan"))]}]:
        p=tmp_path/"contract.json";p.write_text(json.dumps(d|changes))
        with pytest.raises(VFGError): load_document(p,Contract)

def test_verdict_exit_pair():
    with pytest.raises(ValueError): Verdict(verdict="PASS",exit_code=2)

def test_exported_schemas_match():
    from pathlib import Path
    from vfg.schema import SCHEMAS
    for name,model in SCHEMAS.items():
        assert json.loads(Path(f"schemas/{name}.schema.json").read_text())==model.model_json_schema()

