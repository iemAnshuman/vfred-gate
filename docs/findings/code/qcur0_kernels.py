"""Rebuild Qcur-0 (layer 0 attn_q MUL_MAT, Q8_0 weight) the way three ggml CPU kernels compute it.

Usage:
  python qcur0_kernels.py MODEL.gguf ACTIVATION.f32 NAME=CAPTURE.f32 [NAME=CAPTURE.f32 ...]

ACTIVATION.f32 is the captured `attn_norm-0` payload (960 floats); each CAPTURE.f32 is a captured
`Qcur-0` payload. The script quantises the activation to Q8_0, computes the dot products in the
summation order of each kernel at llama.cpp 552f18f, and prints how many of the 960 outputs differ
bit-wise from each capture.
"""

import struct
import sys

import numpy as np

f32 = np.float32


def read_q8_0(path, name):
    f = open(path, "rb")

    def r(fmt):
        return struct.unpack(fmt, f.read(struct.calcsize(fmt)))

    def rs():
        (n,) = r("<Q")
        return f.read(n).decode()

    def rv(t):
        if t == 8:
            return rs()
        if t == 9:
            (et,) = r("<I")
            (n,) = r("<Q")
            return [rv(et) for _ in range(n)]
        return r("<" + {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}[t])[0]

    _, _, n_tensors, n_kv = r("<4sIQQ")
    align = 32
    for _ in range(n_kv):
        key = rs()
        (t,) = r("<I")
        value = rv(t)
        if key == "general.alignment":
            align = value
    info = {}
    for _ in range(n_tensors):
        tname = rs()
        (nd,) = r("<I")
        dims = r("<" + "Q" * nd)
        ty, off = r("<IQ")
        info[tname] = (dims, ty, off)
    base = (f.tell() + align - 1) // align * align
    (k, n), ty, off = info[name]
    assert ty == 8, "expected a Q8_0 tensor"
    nb = k // 32
    f.seek(base + off)
    raw = np.frombuffer(f.read(n * nb * 34), dtype=np.uint8).reshape(n, nb, 34)
    scales = raw[:, :, :2].copy().view("<f2").reshape(n, nb).astype(f32)
    quants = raw[:, :, 2:].view(np.int8).astype(np.int32)
    return scales, quants


def quantise(x, mode):
    """Q8_0 activation quantisation: "ref" (id = 1/d, roundf), "neon" (id = 1/d, round to even) or "x86" (id = 127/amax, round to even)."""
    amax = np.max(np.abs(x), axis=1).astype(f32)
    d = (amax / f32(127)).astype(f32)
    if mode == "x86":
        inv = np.where(amax != 0, f32(127) / amax, f32(0)).astype(f32)
        q = np.rint((x * inv[:, None]).astype(f32))
    elif mode == "neon":
        inv = np.where(d != 0, f32(1) / d, f32(0)).astype(f32)
        q = np.rint((x * inv[:, None]).astype(f32))
    else:
        inv = np.where(d != 0, f32(1) / d, f32(0)).astype(f32)
        v = (x * inv[:, None]).astype(f32).astype(np.float64)
        q = np.where(v >= 0, np.floor(v + 0.5), np.ceil(v - 0.5))
    return q.astype(np.int32), d.astype(np.float16).astype(f32)


def fma(a, b, c):
    return (a.astype(np.float64) * b.astype(np.float64) + c.astype(np.float64)).astype(f32)


def dot_scalar(wd, wq, q, dy):
    """quants.c generic ggml_vec_dot_q8_0_q8_0: sequential, sumf += sumi * (dx * dy), no FMA."""
    sumi = (wq * q[None]).sum(2)
    sc = (wd * dy[None]).astype(f32)
    acc = np.zeros(wd.shape[0], f32)
    for b in range(wd.shape[1]):
        acc = (acc + (sumi[:, b].astype(f32) * sc[:, b]).astype(f32)).astype(f32)
    return acc


def dot_x86(wd, wq, q, dy):
    """arch/x86 AVX2: 8 lanes of 4-product int sums, _mm256_fmadd_ps per block, then hsum_float_8."""
    n, nb = wd.shape
    lanes = (wq * q[None]).reshape(n, nb, 8, 4).sum(3)
    sc = (wd * dy[None]).astype(f32)
    acc = np.zeros((n, 8), f32)
    for b in range(nb):
        acc = fma(np.broadcast_to(sc[:, b, None], acc.shape), lanes[:, b].astype(f32), acc)
    h = (acc[:, :4] + acc[:, 4:]).astype(f32)
    h = (h[:, :2] + h[:, 2:]).astype(f32)
    return (h[:, 0] + h[:, 1]).astype(f32)


def dot_neon(wd, wq, q, dy):
    """arch/arm NEON without dotprod: two 4-lane accumulators (even/odd blocks), unfused vmlaq_n_f32, vaddvq_f32."""
    n, nb = wd.shape
    products = wq * q[None]
    lanes = np.zeros((n, nb, 4), np.int64)
    for half in (0, 16):
        for j in range(4):
            lanes[:, :, j] += (products[:, :, half + 2 * j] + products[:, :, half + 2 * j + 1]
                               + products[:, :, half + 8 + 2 * j] + products[:, :, half + 9 + 2 * j])
    sc = (wd * dy[None]).astype(f32)
    acc = [np.zeros((n, 4), f32), np.zeros((n, 4), f32)]
    for b in range(nb):
        k = b & 1
        acc[k] = (acc[k] + (lanes[:, b].astype(f32) * sc[:, b, None]).astype(f32)).astype(f32)

    def addv(a):
        return ((a[:, 0] + a[:, 1]).astype(f32) + (a[:, 2] + a[:, 3]).astype(f32)).astype(f32)

    return (addv(acc[0]) + addv(acc[1])).astype(f32)


def main(argv):
    if len(argv) < 4:
        sys.exit(__doc__)
    wd, wq = read_q8_0(argv[1], "blk.0.attn_q.weight")
    x = np.fromfile(argv[2], "<f4").reshape(wd.shape[1], 32)
    captures = {}
    for item in argv[3:]:
        name, path = item.split("=", 1)
        captures[name] = np.fromfile(path, "<f4")[: wd.shape[0]]
    q_ref, d_ref = quantise(x, "ref")
    q_neon, d_neon = quantise(x, "neon")
    q_x86, d_x86 = quantise(x, "x86")
    same = np.array_equal(q_ref, q_neon) and np.array_equal(q_ref, q_x86)
    print(f"activation quantisation identical in all three kernels: {same}")
    kernels = {
        "scalar (generic, RISC-V rv64gc)": dot_scalar(wd, wq, q_ref, d_ref),
        "x86 AVX2": dot_x86(wd, wq, q_x86, d_x86),
        "ARM NEON, no dotprod": dot_neon(wd, wq, q_neon, d_neon),
    }
    for kname, out in kernels.items():
        diffs = ", ".join(f"{c} {int(np.count_nonzero(out.view('<u4') != y.view('<u4')))}" for c, y in captures.items())
        print(f"{kname}: differing outputs of {wd.shape[0]} vs {diffs}")


if __name__ == "__main__":
    main(sys.argv)
