# ADR 0002: completion scope for the November submission

Status: accepted 6 November 2026.

## Context

The midterm ledger accepts 51 of 100 engineering points. Seven points are blocked on
physical RVV hardware (W0.board, W3.rvv). The remaining 42 points cover work that the
synopsis planned for later phases. The November deadline does not add hardware, a second
conformant implementation, or independent external reviewers.

Some of the deferred work has a component that can be completed honestly on the host and
the QEMU RVV emulator, and a component that cannot. Keeping each item as one indivisible
credit would either overstate the host/emulator evidence or hide work that was actually
done.

## Decision

Split three work items into an achievable component and an explicitly blocked component.
The W0-W9 totals and the 100-point rubric do not change.

| Original item | Component | Points | Completion rule |
|---|---|---:|---|
| W5.instruction (12) | W5.mechanism | 4 | Reproducible emulator policy evidence, static site identity, dynamic execution count and toggle. Not model-level attribution. |
| | W5.model | 8 | Blocked: a model token must be traced to a model instruction, which needs full-model RVV execution. |
| W7.legal (12) | W7.replay | 8 | Legal-tree envelope, QEMU containment, negative control and an independent sampler. |
| | W7.independent | 4 | Blocked: no second conformant hardware implementation or board. |
| W8.hardening (10) | W8.search | 6 | A 1-minimal hardening set restores the contract after a clean rebuild. |
| | W8.cost | 4 | Blocked unless a clean-build cost comparison is defensible; host timing is not presented as RVV evidence. |

W6.prediction (6) remains one item because the host canary study can satisfy its stated
evidence: a frozen selection rule, an untouched holdout and raw recall/cost counts.

## Consequences

- The ledger is versioned and records the new component IDs. The original item names and
  the total remain visible in the plan and the final report.
- A component is accepted only with its own evidence. A failed component stays deferred;
  it is not merged into an accepted sibling.
- W5.mechanism is worth 4, not 12, because the evidence is a probe-level mechanism result.
  The final report must not describe it as model-level causal attribution.
- W7.replay is worth 8, not 12, because QEMU is one implementation and the envelope is
  sampled from a model of the specification.
- Every new accepted component is listed with its evidence path in `docs/progress.yaml`
  and rechecked by `scripts/verify_completion.py`.

## Rejected alternatives

- Accepting W7 or W8 whole on host evidence: overstates the claim.
- Leaving all components deferred: hides completed engineering and understates the work.
- Adding synthetic hardware or emulator claims: prohibited by the project's evidence rules.
