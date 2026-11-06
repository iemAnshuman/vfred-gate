# Five-minute demo

This is the short live demo. The full reproduction is in [demo.md](demo.md).

Run it with:

```sh
bash scripts/demo.sh
```

Each step takes about 100 seconds on the recorded host. To save time in a live session,
run the script before the session and open the three reports.

## The three steps

All three steps use the same four prompts (`c001`, `c007`, `c013`, `c019`) and the same
contract (`contracts/smoke-self-check-v1.json`).

| Step | Plan | Candidate build | Expected verdict |
|---|---|---|---|
| 1 | `plans/smoke.json` | the baseline build again | PASS, exit 0 |
| 2 | `plans/contractfast-smoke.json` | global `-ffp-contract=fast` | FAIL, exit 2 |
| 3 | `plans/selective-smoke.json` | `-ffp-contract=fast`, but `ggml-cpu/ops.cpp` strict | PASS, exit 0 |

## What to say

1. Step 1 shows that the gate is stable. The same build gives the same tokens and bits.
2. Step 2 shows a compiler flag that many teams turn on for speed. The model output
   changes. The gate fails it and the report shows the first token that differs.
3. Step 3 shows the fix. The ddmin search found one file, `ggml-cpu/ops.cpp`, out of
   nine candidate sites. Only that file keeps strict floating-point. The gate passes.
4. The research part: on RISC-V Vector, `vfredusum.vs` may legally return different
   sums. The legal-tree envelope (`scripts/envelope_evidence.py`) computes every legal
   result, so the gate can tell a legal difference from a bug. QEMU stays inside the
   envelope on all 24 probe records.
5. The hardware part: on Rostam's RISC-V board, the unordered sum differed from the
   ordered sum on 13,269 of 20,000 arrays, the same in all five runs. Every checked
   result was legal. See `docs/final-report.md` section 4.0.

## Limits to state

- The three demo runs are on the host CPU. The board result is a separate probe, not a
  model run.
- The board implements RVV 0.7.1, not RVV 1.0.
- The step 3 result covers these four prompts. The 32-case run in `demo.md` section 7 is
  the stronger evidence.
