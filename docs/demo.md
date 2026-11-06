# VFRED-Gate walkthrough

This walkthrough reproduces the final evidence. It assumes macOS or Linux, Python 3.11+,
uv, CMake, Ninja, a C++17 compiler, LLVM tools (`clang`, `ld.lld`, `llvm-objdump`) and
QEMU with RISC-V system emulation. Use a new output directory for every experiment.

The host path and the RVV emulator path are separate. The commands below label which one
produced each result.

## 1. Install and bootstrap

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
```

Bootstrap downloads the pinned llama.cpp archive and the pinned GGUF model, then verifies
the SHA-256 values in `third_party/llama.lock.json` and `models/model.lock.json`. It never
selects a moving revision.

Build the native runner and the host microbench:

```sh
uv run vfg build --stack stacks/baseline.json
cmake --preset host-debug
cmake --build --preset host-debug
ctest --test-dir build/host-debug --output-on-failure
```

Expected: a runner hash in `stacks/baseline.json`, a microbench self-test, and no CTest
failures.

## 2. Smoke qualification and offline report

```sh
uv run vfg qualify --plan plans/smoke.json --output runs/demo
uv run vfg verify --run runs/demo
uv run vfg report --run runs/demo --offline --output runs/demo/report
```

Expected: PASS, exit 0, 4 cases, 40 fresh executions. The report recomputes metrics from
archived `logits.f32`, not from saved totals. Open `runs/demo/report/index.html`.

## 3. Confirmation and compiler comparison

```sh
uv run vfg qualify --plan plans/self-check.json --output runs/self-check
uv run vfg qualify --plan plans/native-comparison.json --output runs/native-comparison
```

Expected: the self-check is bit-equal across 160 fresh executions. The compiler comparison
uses Apple Clang 17 and Homebrew Clang 23; both are bit-equal on the 16-case pilot. These
runs take several minutes each (about 5 and 9 minutes on the recorded host).

## 4. RVV probe and emulator search

```sh
uv run vfg microbench --target targets/rvv-emulator.json --output runs/mechanism
uv run python scripts/rvv_search.py --output runs/mechanism-search
```

Expected: the probe produces 140 records from 28 fixture/length pairs; ordered equals the
scalar left fold and the five repetitions are stable. The search runs 20,000 deterministic
arrays and reports `found: false`: QEMU 11.1.3 returns identical ordered and unordered
bits on every trial. That negative result is the evidence; do not edit it into a
divergence.

Inspect the static inventory and the dynamic counts:

```sh
uv run vfg scan --binary runs/mechanism/probe.elf --output runs/mechanism/inventory.json
jq '{found, trials: .search.trials, dynamic}' runs/mechanism-search/manifest.json
```

## 5. Legal-tree envelope

```sh
uv run python scripts/envelope_evidence.py --output runs/legal-envelope
jq '.summary' runs/legal-envelope/envelope.json
```

Expected: 24 records, ordered equals scalar, every QEMU value is inside the envelope, the
independent C++ sampler agrees on all single-chunk records, and all 24 random operand sets
have more than one legal result. The maximum support is around 152,000 distinct values.
Containment is consistency evidence, not a conformance proof.

## 6. Canary study

The exploratory and holdout runs are already frozen by
`prereg/pilot-v1-amendment.md`. The holdout has been used once; do not present a rerun as
an untouched holdout.

```sh
uv run vfg qualify --plan plans/contractfast-exploratory.json --output runs/contractfast-exploratory
uv run vfg qualify --plan plans/contractfast-holdout.json --output runs/contractfast-holdout
uv run vfg canary --exploratory runs/contractfast-exploratory --holdout runs/contractfast-holdout --output runs/canary-study/study.json
jq '.selection.sequence_failure.holdout' runs/canary-study/study.json
```

Expected: 9 of 32 exploratory cases and 5 of 16 holdout cases fail the decision-level
contract. The frozen threshold selects 10 holdout cases, catches all 5 failures, produces
5 false positives, and costs 20.8% of the 48-case pilot executions.

## 7. Selective hardening

```sh
uv run python scripts/harden_search.py
uv run vfg build --stack stacks/selective.json --build-dir build/selective-release \
  --candidate-flags "-ffp-contract=fast" --strict-sources "ggml-cpu/ops.cpp" \
  --reduction-policy selective-contraction
uv run vfg qualify --plan plans/selective-exploratory.json --output runs/selective-exploratory
uv run python scripts/cost_study.py
uv run python scripts/hardening_evidence.py
jq '{minimal_set: .search.minimal_set, selective: .selective_clean_build.verdict}' runs/hardening-evidence/manifest.json
```

Expected: ddmin reduces nine translation-unit sites to `ggml-cpu/ops.cpp`; the clean
selective build passes 320 executions bitwise, while the global fast build fails. The cost
study prints host medians; do not present them as RVV performance evidence.

## 8. Validation and ledger

```sh
uv run python scripts/validate.py
uv run python scripts/freeze_completion.py
uv run python scripts/check_midterm.py --min-points 50
uv run python scripts/verify_completion.py
```

Expected: Ruff, the full pytest suite with no skips, native CTest, a 71/100 accepted ledger,
and a completion verification that names each accepted, blocked and deferred item.

## 9. Submission checks

1. The final report is `docs/final-report.md`.
2. The walkthrough is this file.
3. The traceability table is `docs/requirements-traceability.csv`.
4. `docs/progress.yaml` is regenerated by `scripts/freeze_completion.py`, never hand-edited.
5. `docs/srs.md` is kept locally and is excluded from Git.
6. Hardware-blocked work is reported as blocked; no emulator run earns a board point.
