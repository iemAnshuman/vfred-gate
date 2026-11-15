"""Resolve a build side (pinned, llama.cpp@ref, or a local checkout) to a source tree."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

from .assets import native_root
from .errors import VFGError
from .manifest import atomic_json, digest, file_digest, load_document

UPSTREAM = "https://github.com/ggml-org/llama.cpp"
ARCHIVE = "https://codeload.github.com/ggml-org/llama.cpp/tar.gz/{commit}"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
REF = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")


def cache_root():
    root = os.environ.get("VFG_CACHE")
    return Path(root).expanduser().resolve() if root else Path.home() / ".cache" / "vfred-gate"


def _git(args, cwd=None):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if p.returncode:
        raise VFGError(f"git {' '.join(args)} failed: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout


def resolve_ref(ref):
    """Map a llama.cpp tag, branch or commit to a 40-hex commit."""
    if COMMIT.match(ref):
        return ref
    if not REF.match(ref) or ref.startswith("-"):
        raise VFGError(f"invalid llama.cpp ref: {ref!r}")
    out = _git(["ls-remote", UPSTREAM, f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}"])
    found = {}
    for line in out.decode().splitlines():
        sha, name = line.split("\t", 1)
        found[name] = sha
    for name in (f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}"):
        if name in found:
            return found[name]
    raise VFGError(f"llama.cpp ref not found upstream: {ref}")


def _download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".download")
    with urllib.request.urlopen(url, timeout=300) as response, temp.open("wb") as f:
        shutil.copyfileobj(response, f)
    temp.replace(path)


def _verify_tree(tree, archive):
    """Every file and link of the archive must exist in the tree unchanged, and nothing else."""
    checked = 0
    expected_files = set()
    with tarfile.open(archive) as tf:
        for member in tf:
            if not (member.isfile() or member.issym() or member.islnk()):
                continue
            relative = Path(*Path(member.name).parts[1:])
            expected_files.add(relative.as_posix())
            path = tree / relative
            if member.issym():
                ok = path.is_symlink() and os.readlink(path) == member.linkname
            elif member.islnk():
                target = tree / Path(*Path(member.linkname).parts[1:])
                ok = path.is_file() and not path.is_symlink() and target.is_file() and (
                    path.read_bytes() == target.read_bytes()
                )
            else:
                expected = hashlib.sha256(tf.extractfile(member).read()).digest()
                ok = path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).digest() == expected
            if not ok:
                raise VFGError(f"cached llama.cpp source was modified: {relative}; delete {tree} to re-extract")
            checked += 1
    extra = []
    for directory, dirs, files in os.walk(tree):
        for name in files + [d for d in dirs if (Path(directory) / d).is_symlink()]:
            relative = (Path(directory) / name).relative_to(tree).as_posix()
            if relative not in expected_files:
                extra.append(relative)
    if extra:
        raise VFGError(f"cached llama.cpp source has extra files ({sorted(extra)[0]}, ...); delete {tree} to re-extract")
    return checked


def fetch_commit(commit, expected_sha256=None):
    """Download, check and extract one llama.cpp commit into the cache.

    With no expected hash, the first successful download records the archive hash and
    later uses must match it (trust on first use). The extracted tree is checked against
    the archive on every use.
    """
    root = cache_root() / "sources"
    root.mkdir(parents=True, exist_ok=True)
    archive = root / f"{commit}.tar.gz"
    record_path = root / f"{commit}.json"
    record = load_document(record_path) if record_path.exists() else None
    expected = expected_sha256 or (record or {}).get("archive_sha256")
    if not archive.exists():
        _download(ARCHIVE.format(commit=commit), archive)
    actual = file_digest(archive)
    if expected and actual != expected:
        archive.unlink()
        raise VFGError(
            f"llama.cpp archive hash mismatch for {commit}: expected {expected}, got {actual}. "
            f"If GitHub changed its archive format, delete {record_path} to trust the new archive."
        )
    tree = root / commit
    try:
        if not (tree / "include/llama.h").is_file():
            with tempfile.TemporaryDirectory(dir=root) as temp:
                with tarfile.open(archive) as tf:
                    tf.extractall(temp, filter="data")
                extracted = Path(temp) / f"llama.cpp-{commit}"
                if not (extracted / "include/llama.h").is_file():
                    raise VFGError("archive does not look like a llama.cpp tree")
                if tree.exists():
                    shutil.rmtree(tree)
                extracted.rename(tree)
        files = _verify_tree(tree, archive)
    except (tarfile.TarError, EOFError, OSError) as exc:
        archive.unlink(missing_ok=True)
        raise VFGError(f"cannot read llama.cpp archive for {commit} ({exc}); it was deleted, run again") from exc
    if record is None:
        atomic_json(record_path, {"schema_version": 1, "commit": commit, "archive_sha256": actual})
    return tree, {"kind": "upstream", "commit": commit, "archive_sha256": actual, "verified_files": files}


def local_checkout(path):
    path = Path(path).expanduser().resolve()
    if not (path / "include/llama.h").is_file():
        raise VFGError(f"not a llama.cpp source tree: {path}")
    top = Path(_git(["rev-parse", "--show-toplevel"], cwd=path).decode().strip()).resolve()
    if top != path:
        raise VFGError(f"local llama.cpp tree must be the root of its git checkout: {path}")
    commit = _git(["rev-parse", "HEAD"], cwd=path).decode().strip()
    diff = _git(["diff", "HEAD", "--binary"], cwd=path)
    untracked = _git(["ls-files", "--others", "--exclude-standard", "-z"], cwd=path)
    files = {
        name: file_digest(path / name) for name in sorted(untracked.decode().split("\0")) if name
    }
    identity = {
        "kind": "local",
        "path": str(path),
        "commit": commit,
        "diff_sha256": hashlib.sha256(diff).hexdigest(),
        "untracked_sha256": digest(files),
        "dirty": bool(diff) or bool(files),
    }
    return path, identity


def resolve_side(spec):
    """Return (source_dir, commit, identity) for one side of a comparison."""
    if spec == "pinned":
        lock = load_document(native_root() / "third_party/llama.lock.json")
        tree, identity = fetch_commit(lock["revision"], lock["archive_sha256"])
        return tree, lock["revision"], identity
    if spec.startswith("llama.cpp@"):
        ref = spec.split("@", 1)[1]
        commit = resolve_ref(ref)
        tree, identity = fetch_commit(commit)
        identity["ref"] = ref
        if ref == commit:
            # A raw commit is fetched through the upstream URL but not matched to an upstream ref.
            identity["kind"] = "github-commit"
        return tree, commit, identity
    tree, identity = local_checkout(spec)
    return tree, identity["commit"], identity
