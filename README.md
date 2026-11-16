# VFRED-Gate

**Did your llama.cpp change alter the model's output? If yes, where did it start?**

VFRED-Gate compares two builds of llama.cpp on one GGUF model. It answers three questions and keeps the evidence:

1. **Verdict.** Do the builds give the same greedy tokens under a declared contract? `PASS`, `FAIL`, `INCONCLUSIVE` or `ERROR`, with exit codes 0/2/3/4 for CI.
2. **Location.** If not, which token step, layer and ggml operator differ first? Found by teacher-forced replay, not by guessing.
3. **Evidence.** Every raw logit, request and build identity goes into a hashed bundle. `vfg verify` recomputes the verdict offline.

A "build" can be a llama.cpp release, a commit, a local checkout with uncommitted changes, different compiler flags or different CMake options (for example a SIMD backend on or off).

## Example

Same llama.cpp commit, same model. The candidate adds one compiler flag, `-ffp-contract=fast`:

```sh
vfg compare --model smollm2-360m-instruct-q8_0.gguf --b-cflags "-ffp-contract=fast"
```

```text
FAIL
  token_choice  0.9884  (needs ge 1.0)
  sequence      0.75  (needs ge 1.0)
first difference: prompt c001, token step 0
  tensor Qcur-17, op ROPE, prompt position 1
  max abs error 4.8e-07, max 15 ULP
report: runs/compare-.../report/index.html
```

One flag changed four of sixteen answers (342 of 346 teacher-forced token choices still agree). The first divergent value is in the rotary position embedding (`ROPE`), where fused multiply-add changes the rounding. These numbers come from a real run on an Apple M4 with Apple Clang 17 (16 prompts, 3 repetitions per build, 192 executions). The same comparison on Linux arm64 with GCC 12 also fails (5 of 16 answers change) and also starts at a `ROPE` op.

The terminal shows this summary; standard output carries the full JSON summary for scripts.

**First finding:** the same llama.cpp commit, model and strict flags give different answers on macOS and Linux (6 of 16 prompts). The cause is the compiler's default CPU target: Apple Clang enables the Arm dot-product extension, so ggml repacks Q8_0 weights and uses a different matmul kernel. A Linux build with `-march=armv8.2-a+dotprod` gives the same answers as macOS, and with one more change to RoPE the logits are bit-identical. On an Intel Xeon, turning on AVX-512 changes 5 of 16 answers, starting in the attention `MUL_MAT`. See [the draft write-up](docs/findings/2026-11-same-build-different-answers.md).

## Install

You need Python 3.11.4+, CMake 3.20+, Ninja and a C/C++17 compiler (Clang or GCC). The tool builds llama.cpp itself.

```sh
pip install vfred-gate          # after the v1.0 release; until then use the checkout below
vfg doctor                      # checks the tools
vfg fetch-model                 # optional: the 386 MB demo model, hash-checked
```

From a checkout:

```sh
git clone https://github.com/iemAnshuman/vfred-gate && cd vfred-gate
uv sync
uv run vfg compare --model "$(uv run vfg fetch-model)" --b-cflags "-ffp-contract=fast"
```

## Usage

```sh
# A llama.cpp upgrade
vfg compare --model m.gguf --a llama.cpp@b6500 --b llama.cpp@b6600

# Your local branch, with uncommitted edits, against a release
vfg compare --model m.gguf --a llama.cpp@b6600 --b ~/src/llama.cpp

# AVX2 against AVX-512 on the same x86 machine (GGML_NATIVE stays OFF on both sides)
vfg compare --model m.gguf --b-cmake "-DGGML_AVX512=ON"

# Your own prompts and a stricter contract
vfg compare --model m.gguf --b ~/src/llama.cpp --prompts prompts.txt --contract bit
```

| Option | Meaning |
|---|---|
| `--a`, `--b` | `pinned` (default), `llama.cpp@<tag>` or `llama.cpp@<full 40-character commit>`, or a path to a llama.cpp git checkout |
| `--a-cmake`, `--b-cmake` | Extra CMake options, for example `"-DGGML_NATIVE=ON"` |
| `--a-cflags`, `--b-cflags` | Extra compiler flags |
| `--contract` | `decision` (default): same token at every step and same text. `bit`: identical logits. `sequence`: same text only |
| `--prompts` | Text file (one prompt per line) or JSONL with a `text` field. Default: 16 built-in prompts |
| `--cases`, `--repetitions`, `--max-tokens`, `--context` | Size of the run (defaults 16, 3, 32, 512) |

Output goes to a new directory (`runs/compare-<time>/` by default):

```text
summary.json            verdict, rules, first difference, build identities
report/index.html       static report, works offline
qualification/          sealed evidence bundle (re-derivable with `vfg verify`)
explain/                localisation bundle (only after a FAIL)
setup/                  generated model lock, prompts, contract, stacks and plan
```

Builds are cached in `~/.cache/vfred-gate` (or `$VFG_CACHE`), keyed by source identity, flags and platform.

### Across machines

`vfg compare` runs both builds on one machine. To compare two machines (for example a laptop and a RISC-V board), record a reference on one and check on the other:

```sh
vfg record --model m.gguf --output ref/            # machine A
vfg check --reference ref/ --model m.gguf          # machine B, same model file
```

`check` judges machine B's build against the recorded outputs with the same contract. It cannot localise, because the two binaries are not on one machine. The reference is trusted as given; pass `--reference-sha256 <hash of ref/bundle.json>` to pin a reference you received from someone else.

### In CI

```sh
vfg compare --model m.gguf --a llama.cpp@"$BASE" --b . --output vfg-run
# exit 0 = PASS, 2 = FAIL, 3 = INCONCLUSIVE, 4 = ERROR
```

## How it works

- Each build links a small C++ runner against llama.cpp: CPU only, one thread, batch 1, F32 KV cache, greedy decoding. Every prompt runs several times per build in a fresh process; unstable output gives `INCONCLUSIVE`, never a false `PASS`.
- The `decision` contract also replays the baseline's tokens into the candidate (teacher forcing), so one early difference does not hide later ones.
- After a `FAIL`, `vfg compare` replays the first differing prompt with tensor capture through llama.cpp's eval callback. It finds the first differing layer, then the first differing ggml op inside it. If the two builds have different graphs, it says "not aligned" and reports only the token step.
- Source identity: upstream archives are hash-checked (the first download records the hash) and the extracted tree is checked against the archive before every build; local checkouts record the HEAD commit and hashes of `git diff` and untracked files. The build cache key also holds the compiler and CMake identities, so a toolchain update never reuses an old build.

## How it differs from other tools

| Tool | What it checks |
|---|---|
| llama.cpp `test-backend-ops` | Each ggml op on a backend against the CPU reference |
| llama.cpp `llama-perplexity --kl-divergence` | KL divergence and top-1 agreement over a text set |
| [infer-check](https://pypi.org/project/infer-check/) | Output differences across engines, quantisations and load |
| **VFRED-Gate** | A CI verdict for two full-model builds, the first differing op, and an offline-verifiable evidence bundle |

## The research behind it: RISC-V vector reductions

The name comes from the RISC-V Vector instruction `vfredusum.vs`. It sums a vector in an *unordered* way: the hardware may pick any legal addition tree, so two conformant chips can return different floating-point results. VFRED-Gate started as a study of whether that latitude changes LLM output. Results so far:

- On a T-Head RVV 0.7.1 board (Rostam `sven0`), the unordered reduction differs from the ordered one on 13,269 of 20,000 random arrays, and every checked result lies inside the computed legal-tree envelope.
- QEMU 11.1.3 returns identical results for both instructions on 20,000 arrays, so emulation cannot show this effect.
- A sensitivity-ranked canary set of 10 prompts caught all 5 holdout failures of a `-ffp-contract=fast` build.
- A ddmin search reduced 9 candidate source files to one (`ggml-cpu/ops.cpp`) that restores bit-identical output.

The full research record, with its 100-point ledger and limitations, is in [docs/research](docs/research/index.md).

## Limitations

- CPU backends of llama.cpp only; one sequence and one thread.
- The tool requires a llama.cpp tree from 2025 or later (it needs the public `llama_vocab` API and `vendor/hash`).
- Localisation stops at the ggml operator. It does not name the instruction.
- A `FAIL` means "incompatible under this contract". It does not mean that either build is wrong.

## Licence

MIT. See [LICENSE](LICENSE).
