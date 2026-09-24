#!/usr/bin/env python3
"""Fetch the explicitly locked public source/model; never choose a moving revision."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(url, path, sha=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (sha is None or hashlib.file_digest(path.open("rb"), "sha256").hexdigest() == sha):
        return
    temp = path.with_suffix(path.suffix + ".download")
    urllib.request.urlretrieve(url, temp)
    if sha and hashlib.file_digest(temp.open("rb"), "sha256").hexdigest() != sha:
        temp.unlink()
        raise RuntimeError("download hash mismatch")
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-model", action="store_true")
    args = parser.parse_args()
    lock = json.loads((ROOT / "third_party/llama.lock.json").read_text())
    archive = ROOT / "third_party/llama.tar.gz"
    download(lock["archive_url"], archive, lock["archive_sha256"])
    target = ROOT / "third_party/llama.cpp"
    if not target.exists():
        with tarfile.open(archive) as tf:
            tf.extractall(ROOT / "third_party", filter="data")
        (ROOT / "third_party" / ("llama.cpp-" + lock["revision"])).rename(target)
    if not args.skip_model:
        model = json.loads((ROOT / "models/model.lock.json").read_text())
        download(model["url"], ROOT / "models" / model["filename"], model["sha256"])
    print("Locked dependencies available.")


if __name__ == "__main__":
    main()
