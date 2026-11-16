# Same llama.cpp build, different answers on macOS and Linux

Status: DRAFT, 16 November 2026. Verdicts come from sealed VFRED-Gate bundles. The libm measurements and the tensor capture comparison are separate small programs in `code/`.

## Summary

The same llama.cpp commit, model, prompts and strict floating-point flags gave different greedy answers on macOS and on Linux: 6 of 16 answers changed. The cause is the compiler's default CPU target, not the operating system:

- Apple Clang targets the Apple M1 feature set by default, which includes the Arm dot-product extension (`__ARM_FEATURE_DOTPROD`). GCC and Clang on Linux aarch64 target plain `armv8-a`, which does not.
- ggml decides at compile time from this macro how it stores Q8_0 weights. With `DOTPROD`, it repacks them into an interleaved `q8_0_4x4` layout and multiplies with `ggml_gemv_q8_0_4x4_q8_0`. Without it, it uses `ggml_vec_dot_q8_0_q8_0`. The two kernels add the same products in a different order.
- A Linux build with `-march=armv8.2-a+dotprod` gives the same answers as macOS on all 16 prompts. A second, smaller difference (Apple Clang merges `sinf` and `cosf` into `__sincosf_stret` in RoPE) changes some logit bits but no answer. With both removed, macOS and Linux logits are bit-identical.

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

Within one OS, the two compilers give the same answers. Both macOS compilers define `__ARM_FEATURE_DOTPROD` by default, and neither Linux compiler does (`-dM -E`); see the cause below. Native SIMD flags do not change them on the A725.

## Cause: the default CPU target selects the Q8_0 kernel

**Where the values first differ.** The same pinned runner request (prompt c001, teacher-forced first token, every tensor captured with its values; [`code/capture-c001-request.json`](code/capture-c001-request.json)) ran on the M4 under macOS and under Linux (Docker). [`code/first_diff.py`](code/first_diff.py) compares the two captures. The first three tensors are bit-identical. The first difference is `Qcur-0`, the first matrix multiplication (`MUL_MAT`, layer 0, position 0): 791 of 960 values differ, by at most 1.9e-06.

**Why.** The two compilers define different CPU feature macros by default (`cc -dM -E`). Apple Clang defines `__ARM_FEATURE_DOTPROD`, `__ARM_FEATURE_FP16_VECTOR_ARITHMETIC` and others; GCC 12 on Linux aarch64 defines neither. In ggml, `ggml_cpu_has_dotprod()` is a compile-time check (`ggml-cpu.c:3811`), and with it the Q8_0 weights are repacked to `q8_0_4x4` (`repack.cpp:5111`). The runner logs confirm it: the macOS run prints `repack tensor token_embd.weight with q8_0_4x4` and a 366.56 MiB `CPU_REPACK` buffer; the default Linux run does neither. Batch-1 decoding never uses the llamafile kernel (`llamafile_sgemm` returns false for `n < 2`).

**Tests (Linux builds in Docker on the M4, checked against the macOS reference `runs/ref-m4`):**

| Linux candidate flags | Verdict | Same text | Bundle |
|---|---|---:|---|
| default (`armv8-a`) | FAIL, token choice 0.980 | 10/16 | `cc1d4d35…` |
| `-march=armv8.2-a+fp16` | FAIL, token choice 0.980, the same six prompts | 10/16 | `c6c192ce…` |
| `-march=armv8.2-a+dotprod` | PASS, token choice 1.0 | 16/16 | `638f317b…` |
| `-march=armv8.2-a+dotprod+fp16+fp16fml` | PASS | 16/16 | `5b2c2634…` |

With `+dotprod`, 60 of the 96 recorded logit files are bit-identical to macOS. In the captures, the first remaining difference is in `ROPE` at position 1 (6 of 960 values, at most 3e-08).

**The second, smaller difference: `sin`/`cos` in RoPE.** `ggml-cpu/ops.cpp:6200-6201` computes the rotary embedding with `cosf(theta)` and `sinf(theta)`. Apple Clang merges the two calls into one `__sincosf_stret` call (`otool -tV`). [`code/rope_libm.c`](code/rope_libm.c) computes this model's angles the way ggml does (`theta_scale = powf(100000, -2/64)`, then `theta *= theta_scale`); the angles are bit-identical on both systems.

- Compiled on macOS without `-fno-builtin`, the program calls `__sincosf_stret`, which differs from glibc at 310 values, 31 of them below position 60 (first at position 1, by 1 ULP). This run uses positions 0 to 59.
- With separate calls (`-fno-builtin`), macOS `sinf`/`cosf` and glibc differ only at positions 93 and above. For these angles, glibc's `sincosf` returns the same bits as its `sinf` and `cosf`.
- `-fmath-errno` stops the merge. A macOS reference recorded with `-fmath-errno` (`b0dce9f7…`) selects the same tokens as the default reference in all 96 jobs.

**Bit-identical result.** The Linux `+dotprod` build checked against the `-fmath-errno` macOS reference under the `bit` contract: PASS, all logits bit-identical, 16/16 (bundle `ac203f08…`). Longer contexts reach positions where separate `sinf`/`cosf` also differ, so a third difference can appear there.

**Ruled out on the way.** Two earlier tests tried libm causes and left the verdict unchanged: the `-fmath-errno` reference against the default Linux build (`b53e12df…`), and a softmax patch that replaces libm `expf` at `vec.cpp:595` with ggml's NEON `expf` (`a803b9ad…`, [`code/softmax-no-libm-expf.patch`](code/softmax-no-libm-expf.patch); libm `expf` itself differs between the systems, [`code/expf_scan.c`](code/expf_scan.c)). `GGML_ACCELERATE` and `GGML_BLAS` are off in all builds.

**What this means.** The answers depend on which CPU features the compiler assumes, even when the CPU is the same and all floating-point flags are strict. A generic Linux package and a `-march=native` build on the same Arm server can therefore give different answers. The same happens on x86 when AVX-512 kernels are turned on (Result 4). The other Linux machines in Result 1 fit this: none of their builds defines `DOTPROD`, so none repacks Q8_0 weights, and their own SIMD kernels give their own patterns. This last point was not tested separately.

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

1. Check that x86 and RISC-V Linux builds also match macOS when they use the same Q8_0 kernel order (for example with a repack disabled on macOS).
2. The x86 pattern (EPYC and Xeon agree) differs from the ARM Linux pattern on two prompts (c002, c005 instead of c004, c008). x86 and ARM use different ggml SIMD kernels; this needs its own controls.
3. One model, one quantisation, 16 prompts. Other models may be more or less sensitive.
