"""Legal reduction-tree envelopes for RVV unordered floating-point sums.

The model is deliberately narrow and explicit:

* the scalar seed and the active elements are leaves of a binary addition tree;
* every internal node rounds its exact result to a format at least as precise as
  binary32 (this module models binary32 and binary64);
* the strip-mined chunk boundaries are fixed by ``vl`` and the declared VLMAX;
* round-to-nearest, ties-to-even is the only modelled rounding mode.

Enumerating all parenthesizations and per-node precision choices gives the set of
results this model permits. It is not a proof of the ISA's full latitude: an
implementation may use a wider intermediate format or a tree this model does not
sample. Containment is therefore consistency evidence, never conformance proof.
"""

import struct
import numpy as np

from ..errors import VFGError

DEFAULT_PRECISIONS = (32, 64)
DEFAULT_CHUNK = 8
DEFAULT_CAP = 2_000_000


def f32(value):
    with np.errstate(over="ignore", invalid="ignore"):
        return float(np.float32(value))


def bits_of(value):
    return int.from_bytes(struct.pack("<f", _canonical(f32(value))), "little")


def value_of(bits):
    return struct.unpack("<f", int(bits).to_bytes(4, "little"))[0]


def _canonical(value):
    return 0.0 if value == 0.0 else value


def _rounded(value, precision):
    if precision == 32:
        return _canonical(f32(value))
    if precision == 64:
        return _canonical(float(value))
    raise VFGError(f"unsupported intermediate precision: {precision}")


def subtree_support(values, precisions=DEFAULT_PRECISIONS, cap=DEFAULT_CAP):
    """Exact support of all binary trees and per-node precision choices."""
    if not values:
        raise VFGError("subtree_support requires at least one leaf")
    if any(not np.isfinite(float(v)) for v in values):
        raise VFGError("envelope operands must be finite")
    n = len(values)
    table = [[None] * n for _ in range(n)]
    for i, value in enumerate(values):
        table[i][i] = {_canonical(float(value))}
    for length in range(2, n + 1):
        for start in range(0, n - length + 1):
            end = start + length - 1
            support = set()
            for split in range(start, end):
                left = table[start][split]
                right = table[split + 1][end]
                for a in left:
                    for b in right:
                        total = a + b
                        for precision in precisions:
                            support.add(_rounded(total, precision))
                if len(support) > cap:
                    raise VFGError(f"envelope support exceeds {cap} values")
            table[start][end] = support
    return sorted(table[0][n - 1])


def chunk_envelope(seed, operands, chunk_size=DEFAULT_CHUNK, precisions=DEFAULT_PRECISIONS, cap=DEFAULT_CAP):
    """Support after strip-mining: each chunk is one unordered reduction."""
    operands = [float(v) for v in operands]
    if chunk_size < 1:
        raise VFGError("chunk_size must be positive")
    seeds = {_canonical(float(seed))}
    chunks = [operands[i : i + chunk_size] for i in range(0, len(operands), chunk_size)]
    executed = 0
    for chunk in chunks:
        combined = set()
        for current in seeds:
            combined.update(subtree_support([current] + chunk, precisions, cap))
            executed += 1
            if len(combined) > cap:
                raise VFGError(f"envelope support exceeds {cap} values")
        seeds = combined
    return {
        "model": "seed_and_elements_are_leaves",
        "precisions": list(precisions),
        "chunk_size": chunk_size,
        "chunks": len(chunks),
        "reduction_executions": executed,
        "support": sorted(seeds),
    }


def seed_root_envelope(seed, operands, chunk_size=DEFAULT_CHUNK, precisions=DEFAULT_PRECISIONS, cap=DEFAULT_CAP):
    """Conservative sensitivity model: the scalar seed is added once at the root."""
    operands = [float(v) for v in operands]
    seeds = {_canonical(float(seed))}
    chunks = [operands[i : i + chunk_size] for i in range(0, len(operands), chunk_size)]
    for chunk in chunks:
        combined = set()
        for current in seeds:
            if chunk:
                inner = subtree_support(chunk, precisions, cap)
            else:
                inner = {0.0}
            for value in inner:
                for precision in precisions:
                    combined.add(_rounded(current + value, precision))
            if len(combined) > cap:
                raise VFGError(f"envelope support exceeds {cap} values")
        seeds = combined
    return {
        "model": "seed_added_at_root",
        "precisions": list(precisions),
        "chunk_size": chunk_size,
        "chunks": len(chunks),
        "reduction_executions": sum(1 for chunk in chunks if chunk),
        "support": sorted(seeds),
    }


def contains(envelope, observed_bits):
    observed = _canonical(value_of(observed_bits))
    return observed in set(envelope["support"])


def interval(envelope):
    finite = [v for v in envelope["support"] if np.isfinite(v)]
    if not finite:
        return None
    low = min(finite)
    high = max(finite)
    return {
        "minimum": low,
        "maximum": high,
        "minimum_bits": bits_of(low),
        "maximum_bits": bits_of(high),
    }


def summarize(envelope, observed_bits):
    support = envelope["support"]
    observed = _canonical(value_of(observed_bits))
    interval_info = interval(envelope)
    return {
        "support_size": len(support),
        "observed_bits": int(observed_bits),
        "observed_value": observed,
        "contained": observed in set(support),
        "interval": interval_info,
        "other_legal_examples": [
            {"value": value, "bits": bits_of(value)}
            for value in support
            if value != observed
        ][:3],
        "model": envelope["model"],
        "precisions": envelope["precisions"],
        "chunks": envelope["chunks"],
        "reduction_executions": envelope["reduction_executions"],
    }
