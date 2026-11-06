# VFRED-Gate

Compare LLM inference stacks, check numerical compatibility, and diagnose differences
through replay. The research focus is RISC-V Vector (RVV) floating-point reduction order:
`vfredosum.vs` is ordered, while `vfredusum.vs` may choose a legal reduction tree and
produce a different, still conformant, number.

**Status:** 71/100 engineering points verified. Seven points are blocked on physical RVV
hardware; the remaining gaps are listed in the [final report](docs/final-report.md).
Host and QEMU evidence are labelled separately throughout; no emulator result is presented
as board evidence.

## What works

- Pinned SmolLM2-360M-Instruct Q8_0 model and pinned llama.cpp runner.
- Strict manifests, content-addressed artifacts, and offline re-derivation of verdicts.
- Bit, numeric, decision and sequence contracts with PASS/FAIL/INCONCLUSIVE/ERROR exits.
- RVV reduction microbenchmarks, ELF/DWARF instruction inventory and QEMU execution.
- Teacher-forced replay, layer/operator capture and a seeded diagnostic.
- Legal-tree envelopes for unordered FP32 reductions, with an independent sampler.
- Sensitivity-ranked canary selection with a frozen one-shot holdout.
- ddmin selective hardening, a clean rebuild and host cost measurement.

## Quick start

Install Python 3.11+, uv, CMake, Ninja, a C++17 compiler, LLVM tools and QEMU. Then:

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
uv run vfg build --stack stacks/baseline.json
uv run vfg qualify --plan plans/smoke.json --output runs/demo
uv run vfg verify --run runs/demo
uv run vfg report --run runs/demo --offline --output runs/demo/report
```

Open `runs/demo/report/index.html`. Models, builds and raw bundles stay out of Git;
rebuild locally to reproduce results. Use a new output directory for every run.

## Evidence and walkthrough

- [Final report](docs/final-report.md): results, points, limitations and unverified claims.
- [Walkthrough](docs/demo.md): complete command sequence, including envelope, canary and
  hardening evidence.
- [Midterm report](docs/midterm-report.md): the original 51-point milestone.
- [Progress ledger](docs/progress.yaml): exactly which points are accepted, blocked or
  deferred, with evidence hashes.
- [Completion plan](plans/completion-plan.md): what was attempted and in what order.
- [ADR 0002](docs/adr/0002-completion-scope.md): why three work items were split into an
  achievable and a blocked component.

```sh
uv run python scripts/check_midterm.py --min-points 50
uv run python scripts/verify_completion.py
```

The checker re-derives qualification verdicts from the local `runs/` bundles. A fresh
clone without those bundles reports missing evidence rather than a fabricated PASS.
