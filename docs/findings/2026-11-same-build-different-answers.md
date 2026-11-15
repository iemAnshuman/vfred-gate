# Same llama.cpp build, different answers on macOS and Linux

Status: DRAFT, 16 November 2026. Verdicts come from sealed VFRED-Gate bundles. The libm measurements are separate small C programs in `code/` and are marked as such.

## Summary

The same llama.cpp commit, model, prompts and strict floating-point flags gave different greedy answers on macOS and on Linux: 6 of 16 answers changed. On one ARM CPU (Apple M4), the compiler does not cause it. An Apple M4 under Linux and an ARM Cortex-A725 under Linux diverge from the macOS reference on the same prompts at the same first steps. The cause is not yet known. Two tests with sealed bundles exclude the first candidates: libm `sin`/`cos` in RoPE and libm `expf` in softmax.

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
| ARM Cortex-A725, Rostam `spark-00` | Ubuntu 24.04, glibc 2.39 / GCC 13.3 | 0.980 | 10/16 | c001 (0), c004 (15), c006 (14), c007 (7), c008 (27), c013 (9) | `7c484523…` (Rostam) |
| AMD EPYC 7352, Rostam `buran00` | RHEL 9, glibc 2.34 / GCC 11.5 | 0.980 | 10/16 | c001 (0), c002 (13), c005 (14), c006 (14), c007 (7), c013 (9) | `3227b394…` (Rostam) |
| Intel Xeon Gold 6148, Rostam `medusa00` | RHEL 9, glibc 2.34 / GCC 11.5 | 0.980 | 10/16 | c001 (0), c002 (13), c005 (14), c006 (14), c007 (7), c013 (9) | `1a1ccee6…` (Rostam) |
| T-Head C920 (RVV 0.7.1), Rostam `sven0`, scalar `rv64gc` build | Fedora 38, glibc 2.37 / GCC 13.2 | 0.977 | 10/16 | c001 (0), c005 (14), c006 (5), c007 (7), c011 (0), c013 (9) | `346b8fd9…` (Rostam) |

The M4 under Linux and the Cortex-A725 under Linux diverge on the same six prompts at the same steps. Two different ARM CPUs under Linux diverge from the reference in the same way; one ARM CPU on two operating systems does not give the same answers. The AMD and Intel x86 machines also diverge in the same way as each other, on a pattern that shares four of six prompts with ARM Linux. The RISC-V board (scalar build, no vector kernels) has a third pattern. Prompts c001, c007 and c013 diverge at the same steps on every Linux machine.

## Result 2: controls

| Comparison (same machine) | Verdict | Bundle |
|---|---|---|
| macOS: Apple Clang 17 vs GCC 16 | PASS (16/16, all 346 token choices agree) | `df2bb436…` (local) |
| Linux (Docker on M4): GCC 12 vs Clang 14 | PASS (16/16) | `23fac7bf…` (local) |
| Cortex-A725: `GGML_NATIVE=OFF` vs `ON` (SVE2, i8mm, dotprod) | PASS (16/16) | `77cd5f81…` (Rostam) |
| llama.cpp pinned commit vs release `b12423` (macOS) | PASS (16/16) | local |

The compiler does not change the answers on either OS. Native SIMD flags do not change them on the A725.

## Cause: not yet known

The difference follows the operating system, not the CPU or the compiler. Two C math library (libm) candidates were tested and excluded. Neither test is part of a bundle, except where a bundle is named.

**`sin`/`cos` in RoPE: excluded.** `ggml-cpu/ops.cpp:6200-6201` (pinned commit) computes the rotary embedding with `cosf(theta)` and `sinf(theta)`. Apple Clang merges the two calls into one `__sincosf_stret` call (seen with `otool -tV` in the macOS runner). glibc's `sincosf` returns the same bits as its `sinf` and `cosf`.

- A small C program ([`code/rope_libm.c`](code/rope_libm.c)) computes this model's RoPE angles the way ggml does: `theta_scale = powf(100000, -2/64)` (the model's `rope.freq_base` and head size), then `theta = pos` and `theta *= theta_scale` for each of the 32 pairs, for `pos < 512`. It ran on the M4 under macOS and under Debian 12 (glibc 2.36, arm64, Docker), compiled with `-O2 -ffp-contract=off -fno-builtin`. `theta_scale` and all 16,384 angles are bit-identical on both systems.
- With separate calls, macOS `sinf`/`cosf` and glibc differ only at positions 93 and above. This run uses positions 0 to 59 (prompts of 15 to 28 tokens plus 32 generated tokens).
- macOS `__sincosf_stret` differs from glibc at 31 values below position 60 (first at position 1, by 1 ULP).
- Test: the macOS reference was recorded again with `-fmath-errno`, which stops the merge (the runner then calls `sinf` and `cosf`, and no `__sincosf_stret`). The default Linux build (Docker on the M4) was checked against it. The verdict was unchanged: FAIL, token choice 0.980, 10/16, the same six prompts at the same steps (bundle `b53e12df…`, local; reference `b0dce9f7…`).

**`expf` in softmax: excluded.** An exhaustive scan ([`code/expf_scan.c`](code/expf_scan.c)) shows that macOS libm and glibc `expf` differ somewhere in 41,489 of 273,152 blocks of 4,096 inputs from -0.0 down to -88.0. ggml's softmax (`ggml-cpu/vec.cpp:595`) calls libm `expf` for the elements left over after the NEON loop. A local checkout of the pinned commit with this one call replaced by ggml's own NEON `expf` ([`code/softmax-no-libm-expf.patch`](code/softmax-no-libm-expf.patch)) was recorded on macOS and checked under Linux (Docker on the M4). The verdict was unchanged: FAIL, token choice 0.980, 10/16, the same six prompts at the same steps (bundle `a803b9ad…`, local; reference `bc19ef80…`).

**Not the cause:** `GGML_ACCELERATE` and `GGML_BLAS` are off in all builds, so Apple's Accelerate framework is not used.

**Not yet checked:** other libm calls, the C++ standard library (libc++ against libstdc++), the floating-point environment and memory alignment. The direct way to find the cause is to capture the tensors of one prompt on both systems and compare them op by op. `vfg check` cannot do this yet.

## Result 3: one compiler flag (same machine)

Candidate adds `-ffp-contract=fast` (fused multiply-add allowed).

| Platform | Token choice | Same text | First differing op (`vfg explain`) | Bundle |
|---|---:|---:|---|---|
| macOS, Apple Clang 17 | 342/346 (0.988) | 12/16 | `ROPE` (`Qcur-17`), max 15 ULP | `44e96167…` |
| Linux arm64 (Docker), GCC 12 | 0.987 | 11/16 | `ROPE` (`Qcur-1`) | `a739b682…` |

## Result 4: AVX2 against AVX-512 (same machine)

Intel Xeon Gold 6148 (Rostam `medusa00`), RHEL 9, GCC 11.5, same commit and model. Baseline: default x86 build (`GGML_NATIVE=OFF`, AVX2 and FMA).

| Candidate | Token choice | Same text | First differing op (`vfg explain`) | Bundle |
|---|---:|---:|---|---|
| `-DGGML_AVX512=ON` | 0.985 | 11/16 | `MUL_MAT` (`kq-19`, attention scores), prompt c001, first different token at step 4 | `ed217b9c…` (Rostam) |
| `-DGGML_NATIVE=ON` (includes AVX-512) | 0.985 | 11/16 | `MUL_MAT` (`kq-19`), same case and step | `45e36289…` (Rostam) |

Turning on the AVX-512 kernels changes 5 of 16 answers on the same CPU. The first divergent value is in the attention dot products. The likely mechanism is that wider vectors change the summation order; this was not measured. On the ARM Cortex-A725, the native build (SVE2, i8mm) did not change any answer.

## Open questions

1. Find the first differing op between macOS and Linux with a tensor capture on both systems (see "Cause: not yet known").
2. The x86 pattern (EPYC and Xeon agree) differs from the ARM Linux pattern on two prompts (c002, c005 instead of c004, c008). x86 and ARM use different ggml SIMD kernels; this needs its own controls.
3. One model, one quantisation, 16 prompts. Other models may be more or less sensitive.
