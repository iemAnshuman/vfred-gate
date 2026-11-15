# VFRED-Gate research record

VFRED-Gate began as a university research project on RISC-V Vector (RVV) floating-point reduction order. This folder and the files it links keep that record unchanged. The product documentation is the root [README](../../README.md).

| Document | Content |
|---|---|
| [Final report](../final-report.md) | Results, the 100-point ledger, threats to validity, open questions |
| [Original README](README.md) | The research README at submission (kept byte-identical because the ledger hashes it; its relative links point to the old root) |
| [Progress ledger](../progress.yaml) | Accepted, blocked and deferred items with evidence hashes |
| [Midterm report](../midterm-report.md) | The 51-point milestone |
| [Implementation plan](../../plan.md) | Original design and acceptance criteria |
| [Completion plan](../../plans/completion-plan.md) | Work after the midterm |
| [ADR 0001](../adr/0001-execution-track.md), [0002](../adr/0002-completion-scope.md), [0003](../adr/0003-rvv-0-7-1-board.md) | Execution track, rubric split, RVV 0.7.1 board |
| [Rostam notes](../rostam.md) | Access to the physical RISC-V board |
| [Pre-registration](../../prereg/pilot-v1.md) | Pilot hypotheses and the frozen holdout amendment |
| [Synopsis](../../VFRED-Gate_Synopsis_Report.pdf) | The original project proposal |

Recheck the ledger:

```sh
uv run vfg progress
uv run python scripts/verify_completion.py   # needs the runs/ bundles from the run-results branch
```
