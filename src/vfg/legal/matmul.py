"""A-priori legal-difference envelope for one ggml MUL_MAT output.

The bound documents a difference explained by legal summation order, FMA contraction and the
kernel's rounding of the activation to the weight type's vec_dot type, for F32 and Q8_0 weights
(both accumulate in binary32 in ggml's CPU kernels). F16 weights are not assessed: on Arm targets
with FP16 vector arithmetic, ggml_vec_dot_f16 accumulates in binary16, which this bound does not model. It is conservative and
a-priori: a result inside it is consistent with those causes, never a proof of any ISA behaviour,
and a result outside it does not claim an ISA defect.
"""

import json
from pathlib import Path
import numpy as np
from ..errors import VFGError
from ..gguf import BLOCK, F32, Q8_0, find_tensor, tensor_info, type_name

U = 2.0**-24


def activation_error(x, weight_type):
    """Max rounding error of each x element when converted to the weight type's vec_dot type."""
    if weight_type == F32:
        return np.zeros_like(x)
    if weight_type != Q8_0:
        raise VFGError(f"no envelope for weight type {type_name(weight_type)}")
    blocks = np.abs(x).reshape(x.shape[0], -1, BLOCK).max(axis=2) / 127.0
    scale = blocks.astype(np.float32).astype(np.float16).astype(np.float64)
    return np.repeat(scale / 2.0, BLOCK, axis=1)


def envelope_bound(weights, x, weight_type):
    """Per-output bound B (tokens, rows) for activations x (tokens, K) and weights (rows, K)."""
    k = weights.shape[1]
    if x.shape[1] != k:
        raise VFGError("activation length does not match weight row length")
    if weight_type == Q8_0 and k % BLOCK:
        raise VFGError("Q8_0 reduction length is not a multiple of 32")
    gamma = (k + 2) * U / (1 - (k + 2) * U)
    magnitude = np.abs(weights).T
    s = np.abs(x) @ magnitude
    e = activation_error(x, weight_type) @ magnitude
    return 2.0 * (gamma * s + e)


def assess(out_a, out_b, weights, x, weight_type):
    """Compare two builds' outputs (tokens, rows) against the envelope."""
    if not (np.isfinite(out_a).all() and np.isfinite(out_b).all() and np.isfinite(x).all()):
        return _not_assessed("non-finite values in the outputs or the activation")
    bound = envelope_bound(weights, x, weight_type)
    diff = np.abs(out_a.astype(np.float64) - out_b.astype(np.float64))
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(diff == 0, 0.0, diff / bound)
    outside = int(np.count_nonzero(diff > bound))
    return {
        "status": "outside_envelope" if outside else "inside_envelope",
        "max_ratio": float(ratio.max()) if ratio.size else 0.0,
        "outside_count": outside,
    }


def _not_assessed(reason):
    return {"status": "not_assessed", "reason": reason}


def _events(root):
    return [json.loads(x) for x in (Path(root) / "captures.jsonl").read_text().splitlines()]


def _payload(root, event):
    return np.fromfile(Path(root) / event["payload"], dtype="<f4")


def assess_difference(difference, baseline_root, candidate_root, model_path):
    """Label the first differing tensor; every unmet precondition yields not_assessed with a reason."""
    if difference["op"] != "MUL_MAT":
        return _not_assessed(f"op {difference['op']} is not MUL_MAT")
    src = difference.get("src")
    if not src or len(src) < 2:
        return _not_assessed("capture records carry no input names")
    if difference["shape"][2:] != [1, 1]:
        return _not_assessed("tensor is not 2-D")
    try:
        info = tensor_info(model_path, src[0])
    except VFGError as exc:
        return _not_assessed(str(exc))
    if info is None:
        return _not_assessed(f"{src[0]} is not a model weight")
    if info.type not in (F32, Q8_0):
        return _not_assessed(f"weight type {type_name(info.type)} is not modelled")
    if len(info.ne) != 2:
        return _not_assessed(f"{src[0]} is not a 2-D weight")
    events = {r: _events(root) for r, root in (("a", baseline_root), ("b", candidate_root))}
    own = {r: next((e for e in events[r] if e["ordinal"] == difference["ordinal"]), None) for r in events}
    if not all(own.values()) or not all("payload" in e for e in own.values()):
        return _not_assessed("tensor payload was not captured")
    where = (difference["position"], difference["prediction_step"])

    def activation(role):
        return [
            e
            for e in events[role]
            if e["name"] == src[1]
            and (e["position"], e["prediction_step"]) == where
            and e["ordinal"] < difference["ordinal"]
            and "payload" in e
        ]

    left, right = activation("a"), activation("b")
    if not left or not right:
        return _not_assessed(f"activation {src[1]} was not captured")
    if left[-1]["sha256"] != right[-1]["sha256"]:
        return _not_assessed(f"activation {src[1]} differs between the builds")
    if left[-1]["shape"][2:] != [1, 1]:
        return _not_assessed("activation is not 2-D")
    k, rows = info.ne[0], info.ne[1]
    tokens = difference["shape"][1]
    if difference["shape"][0] != rows or left[-1]["shape"][:2] != [k, tokens]:
        return _not_assessed("shapes do not match a MUL_MAT of the weight and activation")
    try:
        _, weights = find_tensor(model_path, src[0])
    except VFGError as exc:
        return _not_assessed(str(exc))
    x = _payload(baseline_root, left[-1]).astype(np.float64)
    a = _payload(baseline_root, own["a"]).reshape(tokens, rows)
    b = _payload(candidate_root, own["b"]).reshape(tokens, rows)
    result = assess(a, b, weights, x.reshape(tokens, k), info.type)
    result["weight"] = src[0]
    result["weight_type"] = type_name(info.type)
    return result
