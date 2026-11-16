# Changelog

## 1.0.0 (unreleased)

- `vfg compare`: compare two llama.cpp builds on any GGUF model. A side can be `pinned`, `llama.cpp@<tag-or-commit>`, or a local git checkout, with extra CMake options and compiler flags.
- Automatic localisation after a FAIL: first differing token step, layer and ggml operator.
- `vfg explain` and `vfg fetch-model` commands; `vfg doctor` reports missing build tools.
- `vfg record` and `vfg check`: record a reference on one machine and check another machine's build against it, with an optional `--reference-sha256` pin.
- Legality label after a FAIL: when the first differing op is a `MUL_MAT` with an F32 or Q8_0 weight, the outputs are checked against a worst-case rounding bound (`inside_envelope`, `outside_envelope` or `not_assessed`).
- `vfg --version`; `vfg --help` groups the main commands apart from the research-record commands.
- Build cache in `~/.cache/vfred-gate` (or `$VFG_CACHE`) with source identity checks and a lock for parallel runs.
- The model lock accepts any quantisation; the runner builds against any llama.cpp tree from 2025 or later.
- The wheel bundles the native runner sources, so `pip install vfred-gate` works outside a checkout.
- CI on Linux x86-64, Linux arm64 and macOS arm64; Dockerfile.
- The research record moved behind `docs/research/`; its ledger and evidence are unchanged.
- Finding: the same llama.cpp build gives different greedy answers on macOS and Linux, and on x86 and RISC-V; see `docs/findings/`.

## 0.1.0 (12 November 2026)

- Research submission: 75/100 points of the project ledger. See `docs/final-report.md`.
