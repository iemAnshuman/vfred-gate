import json
from pathlib import Path
import tempfile
from ..errors import VFGError
from ..execute import execute_runner
from ..manifest import atomic_json, canonical, file_digest, load_document, now
from ..schema import CorpusCase, ModelLock, Target

def read_corpus(path):
    cases=[]
    try:
        for line in Path(path).read_text().splitlines():
            if line.strip():
                cases.append(CorpusCase.model_validate(json.loads(line)))
    except (ValueError,OSError) as exc:
        raise VFGError(f"invalid corpus: {exc}") from exc
    if not cases or len({x.id for x in cases})!=len(cases):
        raise VFGError("empty corpus or duplicate case IDs")
    groups={}
    for case in cases:
        if case.group_id in groups and groups[case.group_id]!=case.split:
            raise VFGError("group leaks across splits")
        groups[case.group_id]=case.split
    return cases

def freeze_corpus(source,model_lock,binary,output):
    source=Path(source);model_lock=Path(model_lock);output=Path(output)
    if output.exists(): raise VFGError("frozen corpus already exists; create a new version")
    lock=load_document(model_lock,ModelLock)
    model=model_lock.parent/lock.filename
    if file_digest(model)!=lock.sha256: raise VFGError("model digest mismatch")
    rows=[json.loads(x) for x in source.read_text().splitlines() if x.strip()]
    if len({r["id"] for r in rows})!=len(rows): raise VFGError("duplicate source IDs")
    if len({r["text"].strip().casefold() for r in rows})!=len(rows): raise VFGError("duplicate prompt text")
    for r in rows:
        if set(r)!={"id","group_id","category","split","text"}:
            raise VFGError("unexpected source case fields")
    request={"schema_version":1,"mode":"tokenize","model_path":str(model.resolve()),
             "model_sha256":lock.sha256,"texts":[{"id":r["id"],"text":r["text"]} for r in rows],
             "apply_chat_template":True}
    target=Target(id="tokenizer-host",execution_class="host",architecture="native")
    with tempfile.TemporaryDirectory(prefix="vfg-tokenize-") as temp:
        run=Path(temp)/"run"
        execution=execute_runner(binary,request,run,target)
        if execution["status"]!="complete": raise VFGError((run/"stderr.txt").read_text()[-2000:])
        result=load_document(run/"output/result.json")
    mapping={x["id"]:x for x in result["cases"]}
    cases=[]
    for r in rows:
        tokens=mapping[r["id"]]
        cases.append(CorpusCase(id=r["id"],group_id=r["group_id"],category=r["category"],split=r["split"],
                     tokens=tokens["tokens"],model_sha256=lock.sha256,
                     tokenizer_sha256=result["model"]["chat_template_sha256"],
                     formatted_text_sha256=tokens["formatted_text_sha256"]))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(b"".join(canonical(x.model_dump())+b"\n" for x in cases))
    read_corpus(output)
    manifest={"schema_version":1,"frozen_at":now(),"source_sha256":file_digest(source),
              "corpus_sha256":file_digest(output),"model_sha256":lock.sha256,
              "model_revision":lock.revision,"runner_sha256":file_digest(binary),
              "chat_template":result["model"]["chat_template"],
              "chat_template_sha256":result["model"]["chat_template_sha256"],
              "tokenizer_options":{"add_special":True,"parse_special":True,"apply_chat_template":True},
              "cases":len(cases),"splits":{split:[c.id for c in cases if c.split==split] for split in ("exploratory","holdout")},
              "rendered_prompts":{x["id"]:x["formatted_text"] for x in result["cases"]}}
    atomic_json(output.with_suffix(".manifest.json"),manifest)
    return manifest

