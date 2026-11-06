# Pilot v1 amendment: canary holdout evaluation

**Recorded:** 6 November 2026, before any candidate output on the holdout cases.  
**Scope:** host ARM64 study of the W6.prediction claim. Not an RVV hardware result.

## Frozen material

- Model: `models/model.lock.json`, SmolLM2-360M-Instruct Q8_0.
- Corpus: `corpora/pilot-v1.jsonl`; 32 exploratory cases, 16 holdout cases.
- Baseline stack: `stacks/baseline.json` (Apple Clang 17, `-O2 -g -fno-fast-math -ffp-contract=off`).
- Candidate stack: `stacks/contractfast.json` (same source and compiler, declared
  difference `-ffp-contract=fast` on all translation units).
- Candidate binary SHA-256: recorded in `stacks/contractfast.json`.
- Contract level: decision. A case fails when free-running selected tokens or the stop
  reason differ; any bit difference without a token difference is a secondary
  numeric-only outcome, not the primary failure.

The exploratory run is `runs/contractfast-exploratory`: 32 cases, 2 stacks, 5 repetitions.
It produced 9 sequence failures and 32 numeric-only differences. The holdout has not been
executed with any candidate.

## Selection rule (frozen)

1. For every exploratory case, compute the baseline minimum top-two logit margin over all
   generated steps.
2. Rank cases by ascending minimum margin, breaking ties by case ID.
3. Choose the smallest prefix that contains every exploratory sequence failure.
4. Freeze the largest margin in that prefix as the threshold.

Frozen threshold: `0.10355377197265625` (17 of 32 exploratory cases).
The fixed-count companion rule selects the 17 holdout cases with the smallest baseline
minimum margins.

## Holdout evaluation (one shot)

Run `plans/contractfast-holdout.json` once: 16 holdout cases, 2 stacks, 5 repetitions.
Then run:

```sh
uv run vfg canary --exploratory runs/contractfast-exploratory \
  --holdout runs/contractfast-holdout --output runs/canary-study/study.json
```

Primary metrics, with raw counts:

- recall = holdout sequence failures selected by the threshold / all holdout sequence failures;
- false positives = selected holdout cases that did not fail;
- cost ratio = selected holdout cases / 16, and selected cases / 48 total pilot cases;
- Wilson 95% interval for recall.

Secondary: the fixed-count rule, and the same metrics for the numeric-only failure key.
No threshold, case, or metric may be changed after the holdout run. A negative result is
reported as a negative result.

## Analysis identity

- Selection and evaluation code: `src/vfg/canary/study.py`.
- Corpus split manifest: `corpora/pilot-v1.manifest.json`.
- Candidate stack: `stacks/contractfast.json`.
- Holdout plan: `plans/contractfast-holdout.json`.

## Limits

- One model, one quantisation, one host candidate family.
- The candidate changes compiler contraction, not an RVV reduction instruction.
- Token steps within a prompt are dependent; the Wilson interval describes case-level
  recall only, not a generalisation guarantee to other prompts or stacks.
- A holdout used once is no longer untouched for any later analysis.
