"""Fetch the pinned demo model into the cache with a hash check."""

from pathlib import Path
import shutil
import urllib.request

from .assets import native_root
from .errors import VFGError
from .manifest import file_digest, load_document
from .schema import ModelLock
from .sources import cache_root


def fetch_pinned(output=None):
    lock = load_document(native_root() / "models/model.lock.json", ModelLock)
    directory = Path(output).expanduser().resolve() if output else cache_root() / "models"
    path = directory / lock.filename
    if path.is_file() and path.stat().st_size == lock.size_bytes and file_digest(path) == lock.sha256:
        return path
    directory.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".download")
    with urllib.request.urlopen(lock.url, timeout=600) as response, temp.open("wb") as f:
        shutil.copyfileobj(response, f)
    if file_digest(temp) != lock.sha256:
        temp.unlink()
        raise VFGError("downloaded model hash mismatch")
    temp.replace(path)
    return path
