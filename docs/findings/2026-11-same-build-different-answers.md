# Same llama.cpp build, different answers on macOS and Linux

Status: DRAFT, 16 November 2026. Verdicts come from sealed VFRED-Gate bundles. The libm measurements and the tensor capture comparison are separate small programs in `code/`.

## Summary

The same llama.cpp commit, model, prompts and strict floating-point flags gave different greedy answers on macOS and on Linux: 6 of 16 answers changed. On the Apple M4 (macOS against Linux in Docker), the cause is the compiler's default CPU target:

- Apple Clang targets the Apple M1 feature set by default, which includes the Arm dot-product extension (`__ARM_FEATURE_DOTPROD`). GCC and Clang for Linux aarch64 target plain `armv8-a`, which does not.
- With this macro, ggml repacks Q8_0 weights at load time into an interleaved layout and multiplies with a different kernel (`ggml_gemv_q8_0_4x4_q8_0` instead of `ggml_vec_dot_q8_0_q8_0`). The two kernels round differently (grouping, order and fused multiply-add).
- A Linux build with `-march=armv8.2-a+dotprod` gives the same answers as macOS on all 16 prompts. The same build with the repack turned off does not. A second, smaller difference (Apple Clang merges `sinf` and `cosf` into `__sincosf_stret` in RoPE) changes some logit bits but no answer. With both removed, all free-run logits are bit-identical.

The same holds on a second ARM machine (NVIDIA GB10 under Linux): with `+dotprod` or `+dotprod+i8mm`, it gives the macOS answers. The x86 and RISC-V differences have a related cause: each platform's Q8_0 dot-product kernel adds the same exact integer block sums in a different floating-point order (lane layout, fused multiply-add or not). A numpy emulation of the three kernels reproduces the first differing tensor of each platform bit for bit.

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
| NVIDIA GB10 (Cortex-X925 and Cortex-A725 cores), Rostam `spark-00` | Ubuntu 24.04, glibc 2.39 / GCC 13.3 | 0.980 | 10/16 | c001 (0), c004 (15), c006 (14), c007 (7), c008 (27), c013 (9) | `7c484523…` (Rostam) |
| AMD EPYC 7352, Rostam `buran00` | RHEL 9, glibc 2.34 / GCC 11.5 | 0.980 | 10/16 | c001 (0), c002 (13), c005 (14), c006 (14), c007 (7), c013 (9) | `3227b394…` (Rostam) |
| Intel Xeon Gold 6148, Rostam `medusa00` | RHEL 9, glibc 2.34 / GCC 11.5 | 0.980 | 10/16 | c001 (0), c002 (13), c005 (14), c006 (14), c007 (7), c013 (9) | `1a1ccee6…` (Rostam) |
| T-Head C920 (RVV 0.7.1), Rostam `sven0`, scalar `rv64gc` build | Fedora 38, glibc 2.37 / GCC 13.2 | 0.977 | 10/16 | c001 (0), c005 (14), c006 (5), c007 (7), c011 (0), c013 (9) | `346b8fd9…` (Rostam) |

The M4 under Linux and the GB10 under Linux diverge on the same six prompts at the same steps. Two different ARM CPUs under Linux diverge from the reference in the same way; one ARM CPU on two operating systems does not give the same answers. The AMD and Intel x86 machines also diverge in the same way as each other, on a pattern that shares four of six prompts with ARM Linux. The RISC-V board (scalar build, no vector kernels) has a third pattern. Prompts c001, c007 and c013 diverge at the same steps on every Linux machine.

## Result 2: controls

| Comparison (same machine) | Verdict | Bundle |
|---|---|---|
| macOS: Apple Clang 17 vs GCC 16 | PASS (16/16, all 346 token choices agree) | `df2bb436…` (local) |
| Linux (Docker on M4): GCC 12 vs Clang 14 | PASS (16/16) | `23fac7bf…` (local) |
| GB10: `GGML_NATIVE=OFF` vs `ON` (GCC 13.3 `-mcpu=native` enables no extra features here, see below) | PASS (16/16) | `77cd5f81…` (Rostam) |
| llama.cpp pinned commit vs release `b12423` (macOS) | PASS (16/16) | local |

Within one OS, the two compilers give the same answers. Both macOS compilers (Apple Clang 17, Homebrew GCC 16) define `__ARM_FEATURE_DOTPROD` by default; GCC 12 on Linux aarch64 and Clang with `--target=aarch64-linux-gnu` do not (`-dM -E`). See the cause below.

## Cause: the default CPU target selects the Q8_0 kernel

**Where the values first differ.** The same pinned runner request (prompt c001, teacher-forced first token, every tensor captured with its values; [`code/capture-c001-request.json`](code/capture-c001-request.json)) ran on the M4 under macOS and under Linux (Docker). [`code/first_diff.py`](code/first_diff.py) compares the two captures. The first three tensors are bit-identical. The first difference is `Qcur-0`, the first matrix multiplication (`MUL_MAT`, layer 0, position 0): 791 of 960 values differ, by at most 1.9e-06.

**Why.** The two compilers define different CPU feature macros by default (`cc -dM -E`). Apple Clang defines `__ARM_FEATURE_DOTPROD`, `__ARM_FEATURE_FP16_VECTOR_ARITHMETIC` and others; GCC 12 on Linux aarch64 defines neither. In ggml, `ggml_cpu_has_dotprod()` is a compile-time check (`ggml-cpu.c:3811`), and with it the Q8_0 weights are repacked to `q8_0_4x4` (`repack.cpp:5111`). The runner logs confirm it: the macOS run prints `repack tensor token_embd.weight with q8_0_4x4` and a 366.56 MiB `CPU_REPACK` buffer; the default Linux run does neither. The runner feeds the prompt and the generated tokens one at a time (`n_batch = n_ubatch = 1`), so the llamafile kernel is never used (`llamafile_sgemm` returns false for `n < 2`).

**Tests (Linux builds in Docker on the M4, checked against the macOS reference, bundle `2a012730…`; all bundles local):**

| Linux candidate flags | Verdict | Same text | Bundle |
|---|---|---:|---|
| default (`armv8-a`) | FAIL, token choice 0.980 | 10/16 | `cc1d4d35…` |
| `-march=armv8.2-a+fp16` | FAIL, token choice 0.980, the same six prompts | 10/16 | `c6c192ce…` |
| `-march=armv8.2-a+dotprod` | PASS, token choice 1.0 | 16/16 | `638f317b…` |
| `-march=armv8.2-a+dotprod+fp16+fp16fml` | PASS | 16/16 | `5b2c2634…` |
| `-march=armv8.2-a+dotprod`, `-DGGML_CPU_REPACK=OFF` | FAIL, token choice 0.986 | 11/16 | `cd224942…` |
| `-march=armv8.2-a+dotprod+i8mm` (repacks to `q8_0_4x8`) | PASS | 16/16 | `aad90421…` |

Turning the repack off brings the failure back, so the repacked kernel is the mechanism, not the dot-product instruction itself. With `+dotprod`, all recorded logits of 10 of the 16 prompts are bit-identical to macOS. In the captures, the first remaining difference is in `ROPE` at position 1 (6 of 960 values, at most 3e-08).

**The second, smaller difference: `sin`/`cos` in RoPE.** `ggml-cpu/ops.cpp:6200-6201` computes the rotary embedding with `cosf(theta)` and `sinf(theta)`. Apple Clang merges the two calls into one `__sincosf_stret` call (`otool -tV`). [`code/rope_libm.c`](code/rope_libm.c) computes this model's angles the way ggml does (`theta_scale = powf(100000, -2/64)`, then `theta *= theta_scale`); the angles are bit-identical on both systems.

- Compiled on macOS without `-fno-builtin`, the program calls `__sincosf_stret`, which differs from glibc at 310 values, 31 of them below position 60 (first at position 1, by 1 ULP). This run uses positions 0 to 59.
- With separate calls (`-fno-builtin`), macOS `sinf`/`cosf` and glibc differ only at positions 93 and above. For these angles, glibc's `sincosf` returns the same bits as its `sinf` and `cosf`.
- `-fmath-errno` stops the merge. A macOS reference recorded with `-fmath-errno` (`b0dce9f7…`) selects the same tokens as the default reference in all 96 jobs.

**Bit-identical result.** The Linux `+dotprod` build checked against the `-fmath-errno` macOS reference under the `bit` contract: PASS, all free-run logits bit-identical (16 prompts, 3 runs each, positions below 60; bundle `ac203f08…`, local). Longer contexts reach positions where separate `sinf`/`cosf` also differ, so a third difference can appear there.

**Ruled out on the way.** Two earlier tests tried libm causes and left the verdict unchanged: the `-fmath-errno` reference against the default Linux build (`b53e12df…`), and a softmax patch that replaces libm `expf` at `vec.cpp:595` with ggml's NEON `expf` (`a803b9ad…`, [`code/softmax-no-libm-expf.patch`](code/softmax-no-libm-expf.patch); libm `expf` itself differs between the systems, [`code/expf_scan.c`](code/expf_scan.c)). `GGML_ACCELERATE` and `GGML_BLAS` are off in all builds.

**What this means.** On the M4, the answers depend on which CPU features the compiler assumes, even with the same CPU and strict floating-point flags. All divergences in Result 1 fall on steps where the top two logits of the reference differ by less than 0.13; the largest is 0.1299 (RISC-V, c011, step 0), the others are below 0.1. Only 18 of the reference's 346 steps have a gap below 0.13. Small rounding changes flip exactly these steps, so a shared divergence pattern shows which steps are fragile; it does not show that two machines compute the same values.

**Second ARM machine: NVIDIA GB10.** The CPU reports `asimddp` and `i8mm` (`lscpu`). But on this node GCC 13.3 with `-mcpu=native` defines the same `__ARM_FEATURE_*` macros as the default target, with no `DOTPROD` and no `MATMUL_INT8` (`gcc -mcpu=native -dM -E`). ggml's own feature test also fails: GCC 13.3 rejects `-mcpu=native+dotprod` (`unknown value 'native+dotprod' for '-mcpu'`), so `GGML_MACHINE_SUPPORTS_dotprod_COMPILED` and `GGML_MACHINE_SUPPORTS_i8mm_COMPILED` are `FALSE` in the CMake cache. The `GGML_NATIVE=ON` build in Result 2 was therefore a generic build: its runner log reports `tensor 'token_embd.weight' (q8_0) (and 290 others) cannot be used with preferred buffer type CPU_REPACK`, and no tensor is repacked. This explains why it matched the generic build. Builds with explicit flags, checked on the GB10 against the macOS reference (`2a012730…`):

| GB10 candidate flags | Repack (runner log) | Verdict | Same text | Bundle |
|---|---|---|---:|---|
| default (`armv8-a`) | none | FAIL, token choice 0.980 | 10/16 | `7c484523…` |
| `-march=armv8.2-a+dotprod` | `q8_0_4x4` | PASS, token choice 1.0 | 16/16 | `d807fb83…` |
| `-march=armv8.2-a+dotprod+i8mm` | `q8_0_4x8` | PASS, token choice 1.0 | 16/16 | `a54b6cbc…` |

All GB10 bundles are on Rostam.

## Cause on x86 and RISC-V: the summation order of the Q8_0 dot product

The x86 machines and the RISC-V board do not repack Q8_0 weights either: their runner logs report `tensor 'token_embd.weight' (q8_0) (and 290 others) cannot be used with preferred buffer type CPU_REPACK`, and `n_batch = 1` rules out the llamafile kernel. They use the same `ggml_vec_dot_q8_0_q8_0` entry point as generic ARM Linux, but each architecture has its own implementation.

**Where the values first differ.** The pinned c001 request was captured on the Xeon, the EPYC and `sven0`. The Xeon and the EPYC captures are identical (all 17,370 tensors have the same SHA-256). The first three tensors (`embd`, `norm-0`, `attn_norm-0`) are bit-identical on every platform. The first difference is again `Qcur-0`:

| Captures compared | Differing values of `Qcur-0` (of 960) | Max abs difference |
|---|---:|---:|
| x86 vs ARM Linux | 796 | 3.8e-06 |
| x86 vs macOS | 815 | 3.0e-06 |
| RISC-V (scalar) vs ARM Linux | 817 | 2.9e-06 |
| RISC-V (scalar) vs macOS | 596 | 9.5e-07 |
| x86 vs RISC-V (scalar) | 822 | 2.9e-06 |

**Emulation.** [`code/qcur0_kernels.py`](code/qcur0_kernels.py) reads `blk.0.attn_q.weight` from the GGUF file, quantises the captured `attn_norm-0` activation to Q8_0, and computes the 960 dot products in each kernel's order. All three kernels quantise this activation to the same values, so only the floating-point accumulation differs:

| Kernel (llama.cpp `552f18f`, `ggml/src/ggml-cpu/`) | Accumulation | Differs from the capture of its own platform |
|---|---|---:|
| Generic scalar, used by the `rv64gc` build (`quants.c:451`, via `arch/riscv/quants.c:479`) | one float sum, `sumf += sumi * (dx * dy)`, no FMA | 0 of 960 (RISC-V) |
| x86 AVX2 (`arch/x86/quants.c:1308`) | 8 lanes of 4-product integer sums, `_mm256_fmadd_ps` per block (`:1339`), then `hsum_float_8` (`:43`) | 0 of 960 (Xeon) |
| ARM NEON without dot product (`arch/arm/quants.c:1150`) | two 4-lane accumulators (even and odd blocks), unfused multiply-add, then a lane sum | 0 of 960 (ARM Linux) |

The same NEON emulation with a fused multiply-add leaves 474 values different from the ARM Linux capture, so the FMA choice alone changes the bits. Each kernel is a valid rounding of the same exact products. As on ARM, these differences flip only the steps where the top two logits are close, which is why each platform family has its own divergence pattern.

**Second-order effect, not needed for `Qcur-0`.** The x86 activation quantiser uses `id = 127/amax` with round-to-even; the reference uses `id = 1/d` with `roundf` (`ggml-quants.c:276`). Over 1,935 captured activations (2.6 million values) of the c001 run, these give different 8-bit values in 10 places; `roundf` and round-to-even differ in 9 places, all exact ties.

A `vfg check` control (an x86 build with AVX, AVX2, FMA and F16C off, so that it uses the generic scalar kernel, checked against the macOS reference) was submitted on Rostam; its result is not yet read.

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

Turning on the AVX-512 kernels changes 5 of 16 answers on the same CPU. The first divergent value is in the attention dot products. The likely mechanism is that wider vectors change the summation order; this was not measured.

## Open questions

1. One model, one quantisation, 16 prompts. Other models may be more or less sensitive.
