# VFRED-Gate: final report

**Submission:** 12 November 2026  
**Branch:** `complete-project`  
**Baseline accepted at midterm:** 51/100  
**Accepted at completion:** 71/100  
**Hardware-blocked:** 7 points  
**Deferred or still unverified:** 22 points

## 1. What this report claims

VFRED-Gate is a self-hosted release gate for numerical compatibility of LLM inference
stacks. This submission delivers:

- a pinned SmolLM2-360M-Instruct Q8_0 runner over a pinned llama.cpp revision;
- a four-verdict contract engine with PASS, FAIL, INCONCLUSIVE and ERROR exit codes;
- native self-check and compiler-comparison evidence;
- ELF/DWARF scanning of RVV reduction instructions;
- teacher-forced replay and operator-level localisation with a seeded diagnostic;
- a spec-aware legal-tree envelope for unordered RVV floating-point reductions,
  validated against QEMU and an independent sampler;
- a sensitivity-ranked canary study with a frozen rule and a one-shot holdout;
- a ddmin search for a selective hardening set, a clean selective rebuild and a host
  cost measurement.

It does **not** claim physical RVV board validation, full-model RVV execution,
instruction-level model attribution, a second conformant implementation, or external
reproduction. Section 7 lists those gaps explicitly.

## 2. Platform and pinned assets

| Item | Value |
|---|---|
| Host | ARM64 macOS, Apple Clang 17.0.0 |
| Second compiler | Homebrew Clang 23.1.1 |
| Inference source | llama.cpp `552f18f912a32ea86edf82e2b76431cb7131538d` |
| Model | SmolLM2-360M-Instruct Q8_0, SHA-256 `48ab3034…0201`, 386,404,992 bytes |
| RVV emulator | QEMU 11.1.3, `rv64,v=true,vlen=256,elen=64`, RVV 1.0 |
| Isolation | one sequence, one thread, batch/microbatch 1, F32 KV, greedy selection |
| Contract levels exercised | bit, decision and sequence |

The host and emulator execution classes are recorded separately in every manifest. No
host result is presented as RVV evidence.

## 3. Midterm baseline re-verified

The checkout did not contain `runs/`, so the midterm evidence was not reproducible by
the checker. The pinned assets were restored from the existing locks, the builds were
repeated, and the smoke, self-check, compiler-comparison, seeded and build-reproducibility
receipts were regenerated before any new claim was made.

| Experiment | Cases | Fresh executions | Result |
|---|---:|---:|---|
| Smoke self-check | 4 | 40 | PASS |
| Confirmation self-check | 16 | 160 | PASS |
| Apple Clang 17 vs Homebrew Clang 23 | 16 | 320 | PASS |
| Seeded diagnostic | 1 | 10 | Expected FAIL |
| QEMU reduction probe | 28 fixture/length pairs | 140 | ordered = scalar; policies agree |

The native compiler comparison is a genuine axis-separation result: two compilers with
different code generation produced identical selected tokens and identical logit bits on
the 16-case pilot. It applies to these prompts and this build, not to all code.

### 3.1 Validation

The final validation receipt records Ruff, 91 pytest tests with zero skips, native CMake
configuration/build and CTest, all with return code 0. The completion checker re-derives
every accepted qualification bundle and localisation bundle, hashes every new receipt,
and reports **71 accepted / 29 unearned** points. `scripts/verify_completion.py` repeats
the new checks independently.

## 4. New results

### 4.1 W5: replay, capture and the emulator negative

Teacher-forced replay and operator capture remain as accepted at midterm. The seeded
diagnostic adds 1000 to element zero of `l_out-0` at prompt position 14 of case `c001`.
Replay uses matching token-history hashes, locates `l_out-0` / `ADD` at event 434, and
restores the baseline after the perturbation is removed. Attribution stops at the
operator boundary: `instruction_site` is null.

A new deterministic search asked whether QEMU's `vfredusum.vs` ever differs from
`vfredosum.vs`:

- 20,000 xorshift64 arrays, lengths 2-32, exponents -8 to 8;
- 28 structured probe cases with lengths 0, 1, 4, 7, 8, 9 and 19;
- 51,247 dynamic invocations of each policy in the search binary;
- static sites found for both instructions;
- zero differing results.

This is a bounded negative result for QEMU 11.1.3, not a claim about all RVV
implementations. It also explains why the envelope study cannot use QEMU as a second
policy implementation. W5.mechanism is therefore deferred and W5.model remains blocked.

### 4.2 W6: canary selection and holdout

The candidate is a real host build of the same source with one declared difference:
`-ffp-contract=fast` on all translation units. It is not an injection and not an RVV
build.

- Exploratory: 32 cases, 2 stacks, 5 repetitions; 9 sequence failures and 32
  numeric-only differences.
- Frozen rule: rank by baseline minimum top-two margin; choose the smallest prefix
  covering every exploratory sequence failure. Threshold `0.10355377197265625`;
  17 of 32 exploratory cases.
- Holdout: 16 cases, 2 stacks, 5 repetitions, run once after the rule was committed.
  Five cases failed the decision-level contract.
- The threshold selected 10 holdout cases, caught all 5 failures, and produced 5 false
  positives: recall 1.0 (Wilson 95% 0.566-1.0), precision 0.5.
- Cost: 10 of 16 holdout cases (0.625), or 10 of the 48 pilot cases (0.208).

The result supports H1 on this candidate family: a 10-case suite caught every observed
holdout failure at about 21% of the full-pilot execution cost. The interval is wide and
the precision is only 0.5, so the result is suggestive, not a generalisation guarantee.

### 4.3 W7: legal-tree envelope

The envelope models the result set permitted by an unordered single-width FP32
reduction:

- the scalar seed and active elements are leaves of a binary addition tree;
- every internal node rounds to binary32 or binary64;
- round-to-nearest, ties-to-even;
- strip-mined chunk boundaries are fixed by `vl` and VLMAX, with the scalar carried.

The implementation computes the exact support by dynamic programming over all
parenthesizations and per-node precision choices. It is not a random sample.

Results on the recorded QEMU probe:

- 24 nonzero records, ordered output equals the scalar left fold on every record;
- QEMU's unordered output is inside the primary envelope on every record;
- 10 of 24 structured records have more than one legal result (maximum support 25);
- 24 deterministic random operand sets all have more than one legal result, with a
  maximum support of 152,139 distinct legal values;
- the wrong-seed control and the next-float-above-the-interval control are both rejected;
- an independent C++ sampler agrees exactly with the Python support on all 16
  single-chunk records.

QEMU returned the same bits for both policies on every record, so the envelope is
validated for containment but not against a second policy implementation. The result is
consistency evidence, not a conformance proof. W7.replay is accepted; W7.independent is
blocked because no second implementation or board is available.

### 4.4 W8: selective hardening

The failing candidate is the global `-ffp-contract=fast` build from W6. The hardening
sites are translation units whose floating-point code can be compiled strictly:

`ops.cpp`, `ggml-cpu.c`, `vec.cpp`, `quants.c`, `repack.cpp`, `binary-ops.cpp`,
`unary-ops.cpp`, `ggml.c`, `ggml-quants.c`.

The search used mixed-object screening builds, then rebuilt the winner from source with
a compiler launcher that applies fast contraction everywhere except:

```
ggml-cpu/ops.cpp
```

Results:

- full set passes the screening contract;
- ddmin reduced 9 sites to 1 in 7 recorded tests;
- the mixed-object minimal set passed all 32 exploratory cases;
- a clean rebuild of the same policy passed the full exploratory contract:
  32 cases, 2 stacks, 5 repetitions, 320 executions, bit equality 1.0;
- the empty set is the global fast build, which fails the same contract, so the set is
  1-minimal;
- a host cost study ran 8 cases x 3 builds x 5 repetitions with 128 generated tokens:
  selective/global-strict median wall ratio 0.935, selective/candidate-fast 0.965,
  candidate-fast/global-strict 0.969. Outputs matched the strict baseline for both
  hardened builds; the fast candidate did not match.

The cost differences are small and plausibly within timing noise. They are reported as
host observations only. W8.search is accepted; W8.cost stays blocked because the
measurement is not RVV evidence and does not support a defensible O4 conclusion.

## 5. Points

| Item | Points | Status | Evidence |
|---|---:|---|---|
| W0.host | 2 | accepted | host reduction tests |
| W0.compile | 2 | accepted | real RVV ELF mapping |
| W0.emulator | 2 | accepted | QEMU probe, 140 records |
| W0.board | 4 | blocked | no compatible board |
| W1.schemas | 3 | accepted | schema/manifest tests |
| W1.artifacts | 3 | accepted | artifact/store tests |
| W1.build | 3 | accepted | fresh build comparison |
| W1.execute | 3 | accepted | executor tests |
| W2.scan | 6 | accepted | ELF/DWARF scanner |
| W3.native | 7 | accepted | real-model runner |
| W3.rvv | 3 | blocked | no full-model RVV |
| W4.metrics | 4 | accepted | metric tests |
| W4.verdicts | 3 | accepted | four-verdict tests |
| W4.end_to_end | 3 | accepted | self-check and compiler runs |
| W5.replay | 2 | accepted | shared-history replay |
| W5.capture | 2 | accepted | layer/operator capture |
| W5.seeded | 2 | accepted | seeded localisation |
| W5.mechanism | 4 | deferred | bounded negative on QEMU |
| W5.model | 8 | blocked | needs full-model RVV |
| W6.pilot | 2 | accepted | frozen 48-case corpus |
| W6.prediction | 6 | accepted | frozen holdout study |
| W7.replay | 8 | accepted | legal envelope |
| W7.independent | 4 | blocked | no second implementation |
| W8.search | 6 | accepted | 1-minimal clean rebuild |
| W8.cost | 4 | blocked | host timing only |
| W9.docs | 2 | accepted | report, README, demo |
| W9.study | 2 | deferred | no external reproduction |
| **Total** | **100** | **71 accepted** | |

Seven points are hardware-blocked (W0.board, W3.rvv). Twenty-two more are blocked or
deferred by missing independent implementations, model-level RVV execution, defensible
RVV cost measurement, or external review.

## 6. Threats to validity

- **Single model and quantisation.** Every model result is SmolLM2-360M-Instruct Q8_0.
- **Host candidate.** The canary and hardening studies use an ARM64 compiler-contraction
  candidate, not an RVV reduction instruction.
- **Translation-unit sites.** W8 hardens source files, not individual reduction sites.
  The result shows the search and clean-rebuild machinery; it does not locate the
  responsible instruction.
- **QEMU policy behaviour.** QEMU returned identical ordered and unordered results on
  every tested input, so the envelope is not challenged by a differing implementation.
- **Sampled specification model.** The envelope models FP32/FP64 intermediates and RNE.
  Wider intermediates and other legal trees are outside the model.
- **Holdout used once.** The original 16-case holdout is no longer untouched.
- **Timing noise.** Host wall-time differences of a few percent are not a performance
  result.
- **Dependent token steps.** Case-level recall is reported; token-level confidence
  intervals would overstate independence.

## 7. What remains unverified

1. Physical-board divergence and the original Phase 0 gate.
2. Full SmolLM2 execution on RVV.
3. A model token traced to a model instruction and confirmed by a single-site toggle.
4. A second conformant implementation and an envelope containment rate on it.
5. An RVV cost comparison of selective versus global hardening.
6. Canary recall on a second model, quantisation or hardware family.
7. External reproduction or independent maintainer review.

## 8. Reproduction

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
uv run vfg build --stack stacks/baseline.json
uv run vfg qualify --plan plans/smoke.json --output runs/demo
uv run vfg verify --run runs/demo
uv run vfg report --run runs/demo --offline --output runs/demo/report
uv run python scripts/rvv_probe.py --output runs/mechanism
uv run vfg microbench --target targets/rvv-emulator.json --output runs/mechanism-copy
uv run python scripts/rvv_search.py --output runs/mechanism-search
uv run python scripts/envelope_evidence.py --output runs/legal-envelope
uv run vfg qualify --plan plans/contractfast-exploratory.json --output runs/contractfast-exploratory
uv run vfg qualify --plan plans/contractfast-holdout.json --output runs/contractfast-holdout
uv run vfg canary --exploratory runs/contractfast-exploratory --holdout runs/contractfast-holdout --output runs/canary-study/study.json
uv run python scripts/harden_search.py
uv run vfg build --stack stacks/selective.json --build-dir build/selective-release --candidate-flags "-ffp-contract=fast" --strict-sources "ggml-cpu/ops.cpp" --reduction-policy selective-contraction
uv run vfg qualify --plan plans/selective-exploratory.json --output runs/selective-exploratory
uv run python scripts/hardening_evidence.py
uv run python scripts/validate.py
uv run python scripts/freeze_completion.py
uv run python scripts/check_midterm.py --min-points 50
```

`check_midterm.py` re-derives qualification bundles from `runs/`; a fresh clone without
those local bundles reports missing evidence rather than a fabricated PASS.
