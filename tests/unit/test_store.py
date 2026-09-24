import json
import shutil
import pytest
from vfg.errors import VFGError
from vfg.store import ArtifactStore, seal_bundle, verify_bundle, safe_child, read_array
from vfg.manifest import file_digest


def test_store_corruption_and_dedup(tmp_path):
    p = tmp_path / "input"
    p.write_bytes(b"evidence")
    store = ArtifactStore(tmp_path / "objects")
    sha = store.put(p)
    assert store.put(p) == sha
    assert store.get(sha).read_bytes() == b"evidence"
    store.path(sha).write_bytes(b"changed")
    with pytest.raises(VFGError):
        store.put(p)
    with pytest.raises(VFGError):
        store.get(sha)


def test_bundle_detached_and_tamper(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    (root / "run.json").write_text('{"complete":true}')
    seal_bundle(root)
    clone = tmp_path / "detached"
    shutil.copytree(root, clone)
    assert verify_bundle(clone)["verified"]
    (clone / "run.json").write_text('{"complete":false}')
    with pytest.raises(VFGError):
        verify_bundle(clone)


@pytest.mark.parametrize("path", ["../secret", "/absolute", "foo/../../other", ""])
def test_paths_rejected(tmp_path, path):
    with pytest.raises(VFGError):
        safe_child(tmp_path, path)


def test_malicious_index_and_incomplete_write(tmp_path):
    (tmp_path / "half.tmp").write_text("unfinished")
    with pytest.raises(VFGError):
        seal_bundle(tmp_path)
    (tmp_path / "half.tmp").unlink()
    (tmp_path / "bundle.json").write_text(json.dumps({"schema_version": 1, "files": {"../outside": {}}}))
    (tmp_path / "bundle.sha256").write_text(file_digest(tmp_path / "bundle.json"))
    with pytest.raises(VFGError):
        verify_bundle(tmp_path)


def test_array_shape_and_digest(tmp_path):
    import numpy as np

    p = tmp_path / "x.f32"
    np.array([1, 2], dtype="<f4").tofile(p)
    result = {"logits_file": "x.f32", "logits_shape": [1, 2], "logits_sha256": file_digest(p)}
    assert read_array(tmp_path, result).tolist() == [[1, 2]]
    result["logits_shape"] = [2, 2]
    with pytest.raises(VFGError):
        read_array(tmp_path, result)
