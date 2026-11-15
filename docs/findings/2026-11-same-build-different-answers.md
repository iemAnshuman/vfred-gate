# Same llama.cpp build, different answers on macOS and Linux

Status: DRAFT, 16 November 2026. Verdicts come from sealed VFRED-Gate bundles. The `sinf`/`cosf` measurement is a separate small C program and is marked as such.

## Summary

The same llama.cpp commit, model, prompts and strict floating-point flags gave different greedy answers on macOS and on Linux: 6 of 16 answers changed. Controls show that the CPU and the compiler do not cause it. The remaining difference is the operating system's C math library. A direct test shows that macOS libm and glibc return different `sinf`/`cosf` bits for the same angles, and ggml computes RoPE with exactly these two functions.

## Setup

- llama.cpp commit `552f18f912a32ea86edf82e2b76431cb7131538d`, CPU backend, built by `vfg` with `-O2 -fno-fast-math -ffp-contract=off`, `GGML_NATIVE=OFF`.
- Model: SmolLM2-360M-Instruct Q8_0 (SHA-256 `48ab3034…0201`).
- 16 prompts from `corpora/source/pilot.jsonl`, 32 generated tokens, greedy, one thread, F32 KV cache, 3 repetitions per build (every build was bitwise stable across its repetitions).
- Contract `decision`: the candidate must choose the baseline's token at every teacher-forced step and produce the same text.

## Result 1: cross-machine checks against a macOS reference

Reference: `vfg record` on an Apple M4, macOS, Apple Clang 17. Candidates: `vfg check` with the same commit, flags and model.

| Candidate | OS / compiler | Token choice | Same text | Prompts that diverge (first differing step) | Bundle |
|---|---|---:|---:|---|---|
| Apple M4 | macOS / Apple Clang 17 | 1.0 | 16/16 | none | `cde8a89e…` (local) |
| Apple M4 (Docker) | Debian 12, glibc 2.36 / GCC 12 | 0.980 | 10/16 | c001 (0), c004 (15), c006 (14), c007 (7), c008 (27), c013 (9) | `cc1d4d35…` (local) |
| ARM Cortex-A725, Rostam `spark-00` | Ubuntu 24.04 / GCC 13 | 0.980 | 10/16 | c001 (0), c004 (15), c006 (14), c007 (7), c008 (27), c013 (9) | `7c484523…` (Rostam) |
| AMD EPYC 7352, Rostam `buran00` | RHEL 9 / GCC 11 | 0.980 | 10/16 | c001 (0), c002 (13), c005 (14), c006 (14), c007 (7), c013 (9) | `3227b394…` (Rostam) |
| Intel Xeon Gold 6148, Rostam `medusa` | RHEL 9, glibc 2.34 / GCC 11 | 0.980 | 10/16 | c001 (0), c002 (13), c005 (14), c006 (14), c007 (7), c013 (9) | `1a1ccee6…` (Rostam) |
| T-Head C920 (RVV 0.7.1), Rostam `sven0`, scalar `rv64gc` build | Fedora 38 / GCC 13 | running | | | |

The M4 under Linux and the Cortex-A725 under Linux diverge on the same six prompts at the same steps. Two different ARM CPUs on Linux agree; one ARM CPU on two operating systems does not. The AMD and Intel x86 machines also agree with each other, on a pattern that shares four of six prompts with ARM Linux.

## Result 2: controls

| Comparison (same machine) | Verdict | Bundle |
|---|---|---|
| macOS: Apple Clang 17 vs GCC 16 | PASS (16/16, all 346 token choices agree) | `df2bb436…` (local) |
| Linux (Docker on M4): GCC 12 vs Clang 14 | PASS (16/16) | `23fac7bf…` (local) |
| Cortex-A725: `GGML_NATIVE=OFF` vs `ON` (SVE2, i8mm, dotprod) | PASS (16/16) | `77cd5f81…` (Rostam) |
| llama.cpp pinned commit vs release `b12423` (macOS) | PASS (16/16) | local |

The compiler does not change the answers on either OS. Native SIMD flags do not change them on the A725.

## Mechanism: `sinf`/`cosf` in RoPE

`ggml-cpu/ops.cpp:6200-6201` (pinned commit) computes the rotary embedding with the C library:

```c
*cos_theta = cosf(theta) * mscale;
*sin_theta = sinf(theta) * mscale;
```

A small C program (`runs/libm/t.c`, not part of a bundle) evaluated `sinf`/`cosf` on 16,384 RoPE angles (`pos < 512`, 32 frequencies, base 10000), compiled with `-O2 -ffp-contract=off`. With bit-identical angles, macOS libm and glibc 2.36 returned different `sinf` on 225 angles and different `cosf` on 141 angles. Example: angle 0.29995769, `sinf` = 0.29547977 (macOS) and 0.29547980 (glibc).

This fits the macOS/Linux split, but it is not yet proven to be the only cause. Other C library calls on the model path (for example `expf` in scalar tails) have not been checked.

## Result 3: one compiler flag (same machine)

Candidate adds `-ffp-contract=fast` (fused multiply-add allowed).

| Platform | Token choice | Same text | First differing op (`vfg explain`) | Bundle |
|---|---:|---:|---|---|
| macOS, Apple Clang 17 | 342/346 (0.988) | 12/16 | `ROPE` (`Qcur-17`), max 15 ULP | `44e96167…` |
| Linux arm64 (Docker), GCC 12 | 0.987 | 11/16 | `ROPE` (`Qcur-1`) | `a739b682…` |

## Open questions

1. Confirm the op on Linux: replace `sinf`/`cosf` with a correctly rounded implementation in a local llama.cpp checkout and check whether macOS and Linux then agree (`vfg check --b <checkout>`).
2. The x86 pattern (EPYC and Xeon agree) differs from the ARM Linux pattern on two prompts (c002, c005 instead of c004, c008). x86 and ARM use different ggml SIMD kernels; this needs its own controls.
3. The AVX-512 comparisons on the Xeon are running on Rostam.
4. One model, one quantisation, 16 prompts. Other models may be more or less sensitive.
