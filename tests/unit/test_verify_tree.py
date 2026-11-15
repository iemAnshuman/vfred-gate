import io
import os
import tarfile

import pytest

from vfg.errors import VFGError
from vfg.sources import _verify_tree


def _archive(path):
    with tarfile.open(path, "w:gz") as tf:
        data = b"int x;\n"
        info = tarfile.TarInfo("llama.cpp-c/src/a.c")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("llama.cpp-c/src/b.c")
        link.type = tarfile.SYMTYPE
        link.linkname = "a.c"
        tf.addfile(link)


def _tree(tmp_path):
    archive = tmp_path / "a.tar.gz"
    _archive(archive)
    with tarfile.open(archive) as tf:
        tf.extractall(tmp_path / "x", filter="data")
    return tmp_path / "x/llama.cpp-c", archive


def test_symlinks_in_archive_pass(tmp_path):
    tree, archive = _tree(tmp_path)
    assert _verify_tree(tree, archive) == 2


def test_retargeted_symlink_fails(tmp_path):
    tree, archive = _tree(tmp_path)
    (tree / "src/c.c").write_text("x")
    os.remove(tree / "src/b.c")
    os.symlink("c.c", tree / "src/b.c")
    with pytest.raises(VFGError, match="modified"):
        _verify_tree(tree, archive)


def test_extra_file_fails(tmp_path):
    tree, archive = _tree(tmp_path)
    (tree / "src/new.c").write_text("x")
    with pytest.raises(VFGError, match="extra files"):
        _verify_tree(tree, archive)
