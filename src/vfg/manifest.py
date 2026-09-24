"""Canonical identities and strict document loading."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import yaml
from .errors import VFGError


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(value) + b"\n"
    fd, temp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    return _pairs((loader.construct_object(k), loader.construct_object(v)) for k, v in node.value)


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_document(path, schema=None):
    path = Path(path)
    try:
        text = path.read_text()
        if path.suffix == ".json":
            value = json.loads(
                text,
                object_pairs_hook=_pairs,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"nonfinite {x}")),
            )
        else:
            value = yaml.load(text, Loader=UniqueLoader)
        canonical(value)
        return schema.model_validate(value) if schema else value
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise VFGError(f"{path}: {exc}") from exc


def resolve(base, path):
    p = Path(path).expanduser()
    return p.resolve() if p.is_absolute() else (Path(base) / p).resolve()


def diff_manifests(baseline, candidate, allowed):
    left = baseline.model_dump() if hasattr(baseline, "model_dump") else baseline
    right = candidate.model_dump() if hasattr(candidate, "model_dump") else candidate
    planned, unexpected = {}, {}
    for key in sorted(set(left) | set(right)):
        if key in {"id", "schema_version"} or left.get(key) == right.get(key):
            continue
        destination = planned if key in allowed else unexpected
        destination[key] = {"baseline": left.get(key), "candidate": right.get(key)}
    return {"planned": planned, "uncontrolled": unexpected}


def source_digest(root, paths):
    root = Path(root)
    return digest(
        {
            str(p.relative_to(root)): file_digest(p)
            for directory in paths
            for p in sorted((root / directory).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }
    )
