"""Minimal GGUF v3 reader: find one tensor by name and return it as exact float64."""

from dataclasses import dataclass
import struct
import numpy as np
from .errors import VFGError

F32, F16, Q8_0 = 0, 1, 8
TYPE_NAMES = {F32: "F32", F16: "F16", Q8_0: "Q8_0"}
BLOCK = 32
_SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
_STRING, _ARRAY = 8, 9


@dataclass(frozen=True)
class GGUFTensor:
    name: str
    type: int
    ne: tuple
    offset: int


class _Reader:
    def __init__(self, handle):
        self.handle = handle

    def take(self, n):
        data = self.handle.read(n)
        if len(data) != n:
            raise VFGError("truncated GGUF file")
        return data

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        return self.take(self.unpack("<Q")).decode("utf-8", "replace")

    def value(self, kind):
        if kind in _SCALAR:
            return self.unpack(_SCALAR[kind])
        if kind == _STRING:
            return self.string()
        if kind == _ARRAY:
            inner, count = self.unpack("<I"), self.unpack("<Q")
            if inner in _SCALAR:
                self.take(struct.calcsize(_SCALAR[inner]) * count)
                return None
            return [self.value(inner) for _ in range(count)]
        raise VFGError(f"unsupported GGUF value type {kind}")


def _index(path):
    with open(path, "rb") as handle:
        reader = _Reader(handle)
        if reader.take(4) != b"GGUF":
            raise VFGError("not a GGUF file")
        version = reader.unpack("<I")
        if version != 3:
            raise VFGError(f"unsupported GGUF version {version}")
        count, pairs = reader.unpack("<Q"), reader.unpack("<Q")
        alignment = 32
        for _ in range(pairs):
            key = reader.string()
            value = reader.value(reader.unpack("<I"))
            if key == "general.alignment":
                alignment = int(value)
        tensors = {}
        for _ in range(count):
            name = reader.string()
            dims = reader.unpack("<I")
            ne = tuple(reader.unpack("<Q") for _ in range(dims))
            kind, offset = reader.unpack("<I"), reader.unpack("<Q")
            tensors[name] = GGUFTensor(name, kind, ne, offset)
        base = -(-handle.tell() // alignment) * alignment
    return tensors, base


def tensor_info(path, name):
    """Return the GGUFTensor header of one tensor without reading its data, or None if absent."""
    return _index(path)[0].get(name)


def find_tensor(path, name):
    """Return (GGUFTensor, float64 array shaped (rows, ne0) for 2-D or (ne0,) for 1-D) or None if absent."""
    tensors, base = _index(path)
    info = tensors.get(name)
    if info is None:
        return None
    if info.type not in TYPE_NAMES:
        raise VFGError(f"unsupported GGUF tensor type {info.type} for {name}")
    elements = int(np.prod(info.ne))
    start = base + info.offset
    if info.type == F32:
        flat = np.fromfile(path, dtype="<f4", count=elements, offset=start).astype(np.float64)
    elif info.type == F16:
        flat = np.fromfile(path, dtype="<f2", count=elements, offset=start).astype(np.float64)
    else:
        if elements % BLOCK:
            raise VFGError("Q8_0 tensor size is not a multiple of 32")
        blocks = np.fromfile(
            path, dtype=np.dtype([("d", "<f2"), ("q", "i1", (BLOCK,))]), count=elements // BLOCK, offset=start
        )
        flat = (blocks["d"].astype(np.float64)[:, None] * blocks["q"].astype(np.float64)).reshape(-1)
    if flat.size != elements:
        raise VFGError("truncated GGUF tensor data")
    return info, flat.reshape(tuple(reversed(info.ne)))
