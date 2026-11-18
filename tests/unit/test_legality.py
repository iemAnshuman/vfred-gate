import json
import struct
import numpy as np
import pytest
from vfg.errors import VFGError
from vfg.gguf import F16, F32, Q8_0, find_tensor, type_name
from vfg.legal.matmul import assess, assess_difference


def _string(text):
    raw = text.encode()
    return struct.pack("<Q", len(raw)) + raw


def write_gguf(path, tensors):
    """tensors: list of (name, type, ne, raw bytes)."""
    head = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), 3)
    head += _string("general.name") + struct.pack("<I", 8) + _string("t")
    head += _string("tokenizer.scores") + struct.pack("<IIQ", 9, 6, 2) + struct.pack("<ff", 1.0, 2.0)
    head += _string("tokenizer.tokens") + struct.pack("<IIQ", 9, 8, 2) + _string("a") + _string("bc")
    offset, infos, data = 0, b"", b""
    for name, kind, ne, raw in tensors:
        infos += _string(name) + struct.pack("<I", len(ne)) + b"".join(struct.pack("<Q", n) for n in ne)
        infos += struct.pack("<IQ", kind, offset)
        pad = -len(raw) % 32
        data += raw + b"\0" * pad
        offset += len(raw) + pad
    blob = head + infos
    blob += b"\0" * (-len(blob) % 32)
    path.write_bytes(blob + data)


def q8_raw(weights):
    out = b""
    for block in weights.reshape(-1, 32):
        d = np.float16(np.abs(block).max() / 127)
        q = np.round(block / np.float32(d)).astype(np.int8)
        out += d.tobytes() + q.tobytes()
    return out


def test_reader_f32_f16_q8(tmp_path):
    rng = np.random.default_rng(0)
    f32 = rng.standard_normal((3, 64)).astype("<f4")
    f16 = rng.standard_normal((2, 4)).astype("<f2")
    q8 = rng.standard_normal((2, 64)).astype("<f4")
    path = tmp_path / "m.gguf"
    write_gguf(
        path,
        [("a", F32, (64, 3), f32.tobytes()), ("b", F16, (4, 2), f16.tobytes()), ("c", Q8_0, (64, 2), q8_raw(q8))],
    )
    info, a = find_tensor(path, "a")
    assert info.ne == (64, 3) and np.array_equal(a, f32.astype(np.float64))
    assert np.array_equal(find_tensor(path, "b")[1], f16.astype(np.float64))
    _, c = find_tensor(path, "c")
    assert c.shape == (2, 64) and np.abs(c - q8).max() < 0.05
    assert find_tensor(path, "missing") is None


def test_reader_rejects_bad_files(tmp_path):
    path = tmp_path / "m.gguf"
    path.write_bytes(b"nope")
    with pytest.raises(VFGError):
        find_tensor(path, "a")
    write_gguf(path, [("q", 12, (256,), b"\0" * 144)])
    with pytest.raises(VFGError, match="unsupported GGUF tensor type Q4_K for q"):
        find_tensor(path, "q")


def _problem(kind=F32):
    rng = np.random.default_rng(1)
    w = rng.standard_normal((8, 256))
    x = rng.standard_normal((1, 256))
    return w, x


def test_reordered_sum_is_inside():
    w, x = _problem()
    w32, x32 = w.astype(np.float32), x.astype(np.float32)
    forward = np.array([[np.sum(w32[j] * x32[0], dtype=np.float32) for j in range(8)]])
    chunked = np.array(
        [[np.sum([np.sum(w32[j, i : i + 8] * x32[0, i : i + 8], dtype=np.float32) for i in range(0, 256, 8)], dtype=np.float32) for j in range(8)]]
    )
    result = assess(forward, chunked, w32.astype(np.float64), x32.astype(np.float64), F32)
    assert result["status"] == "inside_envelope" and result["outside_count"] == 0
    assert 0 < result["max_ratio"] < 1


def test_perturbation_is_outside():
    w, x = _problem()
    out = x @ w.T
    result = assess(out, out + 0.1, w, x, F32)
    assert result["status"] == "outside_envelope" and result["outside_count"] == 8
    assert result["max_ratio"] > 1


def test_q8_rounding_widens_the_bound():
    w, x = _problem()
    out = x @ w.T
    tiny = out + 0.02
    assert assess(out, tiny, w, x, F32)["status"] == "outside_envelope"
    assert assess(out, tiny, w, x, Q8_0)["status"] == "inside_envelope"


def test_non_finite_is_not_assessed():
    w, x = _problem()
    out = x @ w.T
    bad = out.copy()
    bad[0, 0] = np.nan
    assert assess(out, bad, w, x, F32)["status"] == "not_assessed"


def _capture(root, name, op, ordinal, values, src, shape):
    root.mkdir(parents=True, exist_ok=True)
    payload = f"tensor-{ordinal}.f32"
    np.asarray(values, "<f4").tofile(root / payload)
    import hashlib

    event = {
        "position": 0,
        "prediction_step": 0,
        "ordinal": ordinal,
        "name": name,
        "op": op,
        "shape": shape,
        "sha256": hashlib.sha256(np.asarray(values, "<f4").tobytes()).hexdigest(),
        "payload": payload,
    }
    if src is not None:
        event["src"] = src
    return event


def _bundle(tmp_path, perturb=0.0, src=("w", "x"), op="MUL_MAT", weight_type=F32):
    w, x = _problem()
    w32 = w.astype("<f4")
    path = tmp_path / "m.gguf"
    raw = w32.tobytes() if weight_type == F32 else w32.astype("<f2").tobytes()
    write_gguf(path, [("w", weight_type, (256, 8), raw)])
    out = (x.astype(np.float32) @ w32.T)[0]
    roots = {}
    for role, delta in (("a", 0.0), ("b", perturb)):
        root = tmp_path / role
        events = [_capture(root, "x", "MUL", 0, x[0], None, [256, 1, 1, 1])]
        events.append(_capture(root, "y", op, 1, out + delta, list(src) if src else None, [8, 1, 1, 1]))
        (root / "captures.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
        roots[role] = root
    difference = {k: events[1][k] for k in ("position", "prediction_step", "ordinal", "name", "op", "shape")}
    if src:
        difference["src"] = list(src)
    return difference, roots, path


def test_assess_difference_labels(tmp_path):
    difference, roots, path = _bundle(tmp_path, perturb=1e-9)
    result = assess_difference(difference, roots["a"], roots["b"], path)
    assert result["status"] == "inside_envelope" and result["weight_type"] == "F32"
    (tmp_path / "o").mkdir()
    difference, roots, path = _bundle(tmp_path / "o", perturb=0.1)
    assert assess_difference(difference, roots["a"], roots["b"], path)["status"] == "outside_envelope"


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"op": "ROPE"}, "not MUL_MAT"),
        ({"src": None}, "no input names"),
        ({"src": ("embd", "x")}, "not a model weight"),
        ({"src": ("w", "nope")}, "was not captured"),
    ],
)
def test_not_assessed_paths(tmp_path, kwargs, reason):
    difference, roots, path = _bundle(tmp_path, perturb=1e-9, **kwargs)
    result = assess_difference(difference, roots["a"], roots["b"], path)
    assert result["status"] == "not_assessed" and reason in result["reason"]


def test_not_assessed_unsupported_weight_type(tmp_path):
    difference, roots, path = _bundle(tmp_path, perturb=1e-9)
    write_gguf(path, [("w", 12, (256, 8), b"\0" * 144)])
    result = assess_difference(difference, roots["a"], roots["b"], path)
    assert result["status"] == "not_assessed" and result["reason"] == "weight type Q4_K is not modelled"


def test_type_name_covers_ggml_enum():
    assert [type_name(k) for k in (0, 8, 14, 30, 41)] == ["F32", "Q8_0", "Q6_K", "BF16", "Q1_0"]
    assert type_name(4) == "4" and type_name(99) == "99"


def test_f16_weight_is_not_assessed(tmp_path):
    difference, roots, path = _bundle(tmp_path, perturb=1e-9, weight_type=F16)
    result = assess_difference(difference, roots["a"], roots["b"], path)
    assert result["status"] == "not_assessed" and "F16" in result["reason"]
