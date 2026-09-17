"""Content-addressed artifacts and independently checkable run bundles."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from .errors import VFGError
from .manifest import atomic_json, file_digest, now

def safe_child(root, name):
    root=Path(root).resolve()
    p=PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or not name or "\\" in name:
        raise VFGError(f"unsafe artifact path: {name}")
    candidate=root.joinpath(*p.parts)
    if not candidate.resolve().is_relative_to(root):
        raise VFGError(f"artifact escapes bundle: {name}")
    return candidate

class ArtifactStore:
    def __init__(self, root):
        self.root=Path(root)
    def path(self, sha):
        if not re.fullmatch(r"[0-9a-f]{64}",sha):
            raise VFGError("invalid object hash")
        return self.root/"sha256"/sha[:2]/sha[2:]
    def put(self, source):
        source=Path(source)
        sha=file_digest(source);destination=self.path(sha)
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            if file_digest(destination)!=sha:
                raise VFGError("existing artifact is corrupt")
            return sha
        fd,tmp=tempfile.mkstemp(dir=destination.parent)
        try:
            with source.open("rb") as inp,os.fdopen(fd,"wb") as out:
                shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
            if file_digest(tmp)!=sha:
                raise VFGError("source changed while storing")
            os.replace(tmp,destination)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return sha
    def get(self,sha):
        p=self.path(sha)
        if not p.exists() or file_digest(p)!=sha:
            raise VFGError("artifact missing or corrupt")
        return p

def seal_bundle(root, store=None):
    root=Path(root)
    files={}
    for path in sorted(root.rglob("*")):
        relative=path.relative_to(root).as_posix()
        if relative in {"bundle.json","bundle.sha256"} or relative.startswith("report/"):
            continue
        if path.is_symlink():
            raise VFGError("symlinks are not allowed in evidence bundles")
        if not path.is_file(): continue
        if path.suffix==".tmp":
            raise VFGError("unfinished temporary artifact")
        sha=store.put(path) if store else file_digest(path)
        files[relative]={"sha256":sha,"size_bytes":path.stat().st_size}
    index={"schema_version":1,"sealed_at":now(),"files":files}
    atomic_json(root/"bundle.json",index)
    (root/"bundle.sha256").write_text(file_digest(root/"bundle.json")+"\n")
    return index

def verify_bundle(root, expected_sha=None):
    root=Path(root)
    try:
        sha=file_digest(root/"bundle.json")
        reference=expected_sha or (root/"bundle.sha256").read_text().strip()
        if sha!=reference:
            raise VFGError("bundle index hash mismatch")
        index=json.loads((root/"bundle.json").read_text())
        if index.get("schema_version")!=1 or not isinstance(index.get("files"),dict):
            raise VFGError("unsupported bundle index")
        for name,meta in index["files"].items():
            path=safe_child(root,name)
            if path.is_symlink() or not path.is_file():
                raise VFGError(f"missing regular artifact: {name}")
            if path.stat().st_size!=meta["size_bytes"] or file_digest(path)!=meta["sha256"]:
                raise VFGError(f"artifact hash mismatch: {name}")
        return {"verified":True,"bundle_sha256":sha,"files":len(index["files"]),"index":index}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise VFGError(f"invalid bundle: {exc}") from exc

def read_array(root, result):
    import numpy as np
    path=safe_child(root,result["logits_file"])
    if file_digest(path)!=result["logits_sha256"]:
        raise VFGError("logit digest mismatch")
    shape=result["logits_shape"]
    if len(shape)!=2 or any(type(n) is not int or n<1 for n in shape):
        raise VFGError("invalid logit shape")
    if path.stat().st_size!=4*shape[0]*shape[1]:
        raise VFGError("logit byte count mismatch")
    return np.fromfile(path,dtype="<f4").reshape(shape)

