# Midterm results

Experiments run on 1 October 2026. See [commit chronology](history.md) for the distinction between Git dates and execution timestamps.

## Scope

The host/emulator implementation includes pinned builds, controlled model execution, RVV instruction scanning, numerical comparisons, contract verdicts, replay, layer/operator capture and offline reports.

The progress ledger verifies **51/100 engineering points** against the fixed weights in [plan.md](../plan.md). Seven of the planned 58 points remain blocked by physical-target validation and full-model RVV execution. The remaining 42 cover later research and evaluation. Check the current total with `uv run python scripts/check_midterm.py --min-points 50`.

## Experiments

| Experiment | Independent cases | Fresh executions | Result |
|---|---:|---:|---|
| Native smoke self-check | 4 | 40 | PASS; bit and sequence equality 1.0 |
| Native confirmation self-check | 16 | 160 | PASS; 19,021,824 aligned logit elements equal; sequences match 16/16 |
| Apple Clang 17 versus Homebrew Clang 23 | 16 | 320 | PASS; teacher-forced token choices match 387/387; free-running sequences match 16/16 |
| Seeded diagnostic | 1 | 10 | Expected FAIL; first generated token differs; no logit elements equal at that step |
| QEMU RVV reduction probe | 28 fixture/length pairs | 140 | Ordered matches scalar; five repeats stable; no ordered/unordered output differences |

Both compiler builds used the same ARM64 host, source, model and inference settings. The PASS applies to these prompts and contracts.

Smoke, confirmation and compiler comparison took 61.62, 280.43 and 537.07 seconds respectively. The smoke bundle and report used 145,815,424 bytes. These are session timings; compilation and other tests overlapped parts of the runs.

## Replay and diagnosis

The diagnostic adds 1000 to element zero of `l_out-0` at prompt position 14 in case `c001`. Replay used matching token-history hashes. Layer discovery and operator capture located `l_out-0`, operation `ADD`, at event 434 as the earliest observed difference. One of its 960 float32 values was directly changed.

Capture preserved the output discrepancy. Turning the injection off restored baseline logits and capture hashes. A separate strided-tensor test confirmed that capture hashes depend on logical values rather than allocation padding.

This validates the injected diagnosis path through an operator boundary. Attribution to a machine instruction remains unresolved.

## Targets and builds

The QEMU probe uses RVV 1.0, VLEN 256, SEW 32, LMUL 1, round-to-nearest, unmasked input and a zero seed. Lengths 0, 1, 4, 7, 8, 9 and 19 cover empty input and vector tails. LLVM disassembly finds both reduction policies, and ELF/DWARF maps them to source. Host fixtures demonstrate non-associativity; QEMU produced matching policy outputs on these cases.

On Rostam's `sven0`, GCC lacked vector headers. Clang compiled the RVV probe, but execution raised SIGILL during vector configuration. Full-model RVV execution is pending a compatible target/toolchain. [Probe details](rostam.md).

A fresh native build matched the source identity and compared Mach-O code/data sections. Whole binary hashes differed because debug paths, object timestamps and associated metadata differed. Build manifests retain compiler identities, effective commands, cache snapshots and library listings.

## Validation and evidence

The recorded suite passed **68 tests without skips**, plus Ruff and native CTest. The commands, timestamps and results are in `evidence/midterm/summary.json`. Checks cover invalid inputs, corruption, timeouts, repeatability, numerical edge cases, aligned histories, all four verdicts, instruction scanning, replay and offline verification.

Raw logits and run bundles stay under `runs/`. Small receipts are tracked under `evidence/midterm/`. Both `vfg verify` and `vfg report --offline` recompute the verdict from the archived arrays. Verification has been performed in this workspace; external reproduction is pending.

The 48-prompt pilot has eight categories, 32 exploratory cases and 16 holdouts. It was frozen at 2026-10-01T11:11:29.693717+00:00 before candidate inspection. Only exploratory cases were run. Logit margins are descriptive; canary prediction has not been evaluated.

## Next work

Obtain a compatible physical target, run the full model on RVV, establish operator-to-instruction attribution, implement sampled legal-tree replay with independent validation, test canaries on the holdout, and measure selective-hardening cost.

The walkthrough and traceability table are ready. Submission documents are kept locally; mentor review and signatures are pending.
