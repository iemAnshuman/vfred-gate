# Completion plan: 6-12 November 2026

**Written:** 6 November 2026  
**Branch:** `complete-project`  
**Baseline:** 51/100 accepted, 7 blocked on physical RVV, 42 deferred  
**Deadline:** course submission 12 November 2026

## 1. Verified starting point

Commands run on 6 November 2026:

```sh
uv run python scripts/check_midterm.py --min-points 50   # ERROR: runs/build-reproducibility.json missing
uv run pytest -q                                          # 40 passed, 28 skipped
uv sync --frozen && uv run python scripts/bootstrap.py     # pinned llama.cpp and model restored
uv run vfg build --stack stacks/baseline.json             # runner built
uv run vfg qualify --plan plans/smoke.json --output runs/smoke-v1
uv run vfg verify --run runs/smoke-v1                     # PASS, exit 0
```

The checker failure is a workspace defect, not a changed result: `runs/` is git-ignored and
the archived bundles were not carried into this checkout. The tracked receipt
`evidence/midterm/summary.json` still records the 1 October verdicts and bundle hashes.
Section 2 restores the local raw bundles before any new claim is made.

The working tree contains the pinned model (386,404,992 bytes) and a fresh llama.cpp
snapshot at `552f18f912a32ea86edf82e2b76431cb7131538d`. Both were downloaded from the
existing locks; no new model or revision is introduced.

## 2. What is actually left

### Hardware-blocked, cannot move

| Item | Points | Why it stays blocked |
|---|---:|---|
| W0.board | 4 | The primary RVV board probe raised SIGILL on Rostam. No compatible board is available in this workspace. |
| W3.rvv | 3 | Full SmolLM2 inference has not run on RVV. QEMU user-mode model execution is not attempted; it would be a different execution class and is not a substitute. |

These stay `blocked` with the original reason. No emulator run can clear them.

### Deferred work, assessed against host plus QEMU

| Item | Points | Honest host/QEMU deliverable | Residual gap |
|---|---:|---|---|
| W5.instruction | 12 | QEMU probe with a reproducible ordered/unordered divergence, static site identity, dynamic execution counts and policy-toggle confirmation | No model token traced to a model instruction; no RVV model execution |
| W6.prediction | 6 | Freeze a sensitivity-selection rule, run it on the untouched 16-case holdout, report recall and execution-cost ratio against the full 48-case suite | One host candidate family, not RVV hardware |
| W7.legal | 12 | Spec-aware legal-tree sampler, envelope over captured operands, QEMU containment, negative control, independent second sampler | No second hardware implementation; sampled, not exhaustive |
| W8.hardening | 10 | ddmin/beam search over real hardening sites in a failing host build, clean rebuild of the 1-minimal policy, measured cost against global hardening | Cost measured on ARM64 host, not RVV; site granularity may be coarser than one instruction |
| W9.study | 2 | Final report with results, limitations and unverified claims | External reproduction and independent review cannot be manufactured locally |

### Rubric handling

The 100-point total and the W0-W9 work-item totals do not change. Three items are split
into an achievable engineering component and an explicitly blocked research component so
that partial completion is not rounded up or hidden:

| Original | Split | Points | Status rule |
|---|---|---:|---|
| W5.instruction (12) | W5.mechanism | 4 | accepted only with divergence, static site, dynamic count and toggle evidence |
| | W5.model | 8 | blocked: model-level instruction attribution needs full-model RVV execution |
| W7.legal (12) | W7.replay | 8 | accepted only with sampler, QEMU containment, negative control and independent sampler |
| | W7.independent | 4 | blocked: no second conformant implementation or board |
| W8.hardening (10) | W8.search | 6 | accepted only with a 1-minimal hardening set that restores PASS after a clean rebuild |
| | W8.cost | 4 | blocked unless a defensible clean-build cost comparison is possible; host timing is not RVV evidence |

This split is recorded in `docs/adr/0002-completion-scope.md` before the evidence is
produced. If a component cannot be completed, it stays deferred and the ledger says so.

## 3. Work packages and order

### C0. Restore the local evidence set (no new points)

Rebuild `host-release`, `llvm-release` and `repro-release`; refresh the stack manifests;
regenerate the smoke, self-check, native-comparison, seeded and build-reproducibility
receipts; run the full test suite with model and RVV tests enabled. This is the
prerequisite for every later ledger change.

Acceptance: `check_midterm.py --min-points 50` returns 51 accepted with all 24 existing
items unchanged in meaning; `pytest` has zero skips when model, runner and probe are present.

### C1. W5.mechanism: a real emulator policy divergence (4 points)

1. Extend the freestanding RVV probe with a deterministic search over fixtures and lengths.
2. Find at least one input where `vfredosum.vs` and `vfredusum.vs` disagree on QEMU.
3. Keep ordered output equal to the scalar left fold; record `vtype`, `vl`, fflags and chunking.
4. Scan the ELF, map both instructions to their wrapper source lines and record dynamic
   invocation counts at the wrapper boundary.
5. Toggle only the reduction policy for that input and require the output difference to
   disappear or change in the declared direction; restore the original policy afterwards.
6. Store the search budget and the negative cases, so the result is a bounded finding,
   not an implied universal divergence.

Stop rule: if no divergence is found after the declared deterministic corpus, record a
bounded negative result and leave W5.mechanism deferred. Do not inject a fake difference.

### C2. W7.replay: legal-tree envelope (8 points)

1. Implement `src/vfg/legal/envelope.py` against the RVV 1.0 unordered-reduction freedom:
   any binary tree over the scalar seed and active elements, each internal node rounded to
   at least the element format. Model FP32 and FP64 intermediate rounding explicitly.
2. Generate a deterministic sample of tree shapes and precisions; for small `vl`, enumerate
   all parenthesizations and both precisions exactly.
3. Build the envelope for the QEMU probe records and for captured FP32 operand slices from
   the model; report containment as a set membership, not only a min/max interval.
4. Add a negative control: a value outside the sampled set must be rejected, and a
   deliberately illegal FP16-intermediate result must be labelled outside the legal model.
5. Implement a second, independent sampler in C++ over the same operand files and compare
   the support sets for exhaustive cases.
6. Persist the sampler version, operands, tree counts, precision set, envelope and QEMU
   observation in a sealed receipt.

Acceptance: ordered output equals the scalar left fold; QEMU unordered output is inside
the sampled envelope on every recorded case; the negative control is outside; the two
samplers agree on exhaustive cases. The report states that containment is consistency
evidence, not a conformance proof.

### C3. W6.prediction: canary selection on the holdout (6 points)

1. Build a second real host stack whose declared difference is numerical, not a test
   injection. Candidate axes, in order: `-ffp-contract=fast`, `-ffast-math`, `-O3`.
   The candidate must be a clean, reproducible build with a recorded manifest.
2. Run the 32 exploratory cases on baseline and candidate. If no case fails, try the next
   axis. If none fails, record a bounded negative result and leave W6 deferred.
3. Before touching the holdout, commit the selection rule, the failure definition, the
   recall and cost formulas, and the number of repetitions in `prereg/pilot-v1-amendment.md`.
4. Rank exploratory cases by baseline minimum top-two margin; choose the smallest prefix
   whose predicted failures cover the observed exploratory failures.
5. Run the sealed 16-case holdout exactly once for the selected candidate. Report
   per-case failure, recall, false-positive count, and the execution-cost ratio
   (selected cases / 48 cases) with raw counts.
6. Do not describe the result as an RVV or hardware result. It is a host canary study on
   one model and one candidate family.

Acceptance: frozen rule before holdout access, complete holdout evidence, raw counts,
and a verdict on H1 that can be negative.

### C4. W8.search: selective hardening (6 points)

1. Define hardening sites in the failing host candidate at translation-unit granularity:
   each site is a source file whose floating-point code contributes to the divergence.
2. Implement `vfg harden`: run the qualification, confirm FAIL, harden the full set,
   confirm PASS, then ddmin to a 1-minimal set and confirm PASS again.
3. Rebuild the 1-minimal policy cleanly and rerun the contract. The instrumented or
   mixed-object build is not the reported result.
4. Measure wall time for native candidate, global hardening and selective hardening on a
   fixed case set with repeated fresh processes. Report medians and raw samples; mark the
   comparison as host-only.
5. If the full set cannot restore PASS, stop and report that the site model is incomplete.

Acceptance: ddmin trace, 1-minimality check, clean rebuild identity, PASS after rebuild,
and measured cost samples. W8.cost stays blocked if the protocol cannot separate build
noise from policy cost or if the result would be presented as RVV evidence.

### C5. Documentation and final polish

1. Update README with the final scope, commands and evidence locations.
2. Update `docs/demo.md` to a complete walkthrough including the new envelope, canary and
   hardening commands, with runtimes and expected outputs.
3. Write `docs/final-report.md`: results, negative results, limitations, threats to
   validity, and an explicit list of unverified claims.
4. Update `docs/requirements-traceability.csv` and `docs/progress.yaml` only from sealed
   evidence.
5. Verify a fresh clone: `uv sync --frozen`, build, tests, smoke run, report.
6. Final checker run and full test suite with no skips.

## 4. Order and checkpoints

| Order | Work | Commit checkpoint | Dependency |
|---:|---|---|---|
| 1 | C0 restore evidence | `restore midterm evidence locally` | none |
| 2 | ADR 0002 and rubric split | `record completion scope split` | C0 |
| 3 | C1 divergence probe | `find emulator reduction divergence` | C0 |
| 4 | C2 envelope | `add legal reduction envelope` | C1 operands |
| 5 | C3 candidate build and exploratory failures | `add numerical candidate stack` | C0 |
| 6 | C3 preregistration and holdout | `evaluate canary selection on holdout` | exploratory freeze |
| 7 | C4 hardening search | `add selective hardening search` | C3 candidate |
| 8 | C4 cost measurement | `measure hardening cost` | clean rebuilds |
| 9 | C5 final report and demo | `finalise project documentation` | all accepted evidence |
| 10 | Final verification | `verify completion evidence` | all |

Every checkpoint commits only after its tests and the checker pass for the evidence that
exists at that point. A failed step is recorded in `REPORT.md` and the next independent
step continues.

## 5. Verification commands

```sh
uv sync --frozen
uv run ruff check src tests scripts
uv run pytest -q
uv run python scripts/check_midterm.py --min-points 50
uv run vfg verify --run runs/self-check
uv run vfg report --run runs/self-check --offline --output runs/self-check/report
uv run python scripts/verify_completion.py
```

`verify_completion.py` is added in C5. It rechecks every new receipt and prints the
accepted, blocked and deferred totals with the evidence path for each item.

## 6. Explicit non-goals

- No physical-board claim, no RVV full-model claim, no second-implementation claim.
- No external reproduction claim.
- No fabricated divergence, no synthetic PASS, no reweighting to hide a gap.
- No changes to the pinned model, llama.cpp revision or frozen corpus.
