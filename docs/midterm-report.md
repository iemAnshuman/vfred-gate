# VFRED-Gate mid-semester implementation report

Actual implementation and experiments: 1 October 2026. The September Git dates are a reconstructed schedule, not execution dates.

## Delivered scope

The working software covers the agreed host/emulator milestone: pinned assets and native builds, strict manifests and contracts, controlled external-process execution, content-addressed artifacts, RVV instruction inventory, real-model logits and greedy decoding, seven comparison metrics, four verdicts, teacher-forced replay, layer/operator capture, seeded localisation, a frozen pilot corpus, offline reports and an evidence-backed progress ledger.

The accepted engineering score is **51/100**, subject to successful verification with `scripts/check_midterm.py`. This is the rubric fixed in `plan.md`, not a percentage of research hypotheses proved. The original 58-point target loses four physical-board points and three full-model RVV points. The remaining 42 points concern later causal attribution, prediction, legal-tree replay, hardening and final study work.

## Actual experiments

| Experiment | Independent cases | Fresh executions | Observed result |
|---|---:|---:|---|
| Native smoke self-check | 4 | 40 | PASS; bit equality and sequence equality 1.0 |
| Native confirmation self-check | 16 | 160 | PASS; 19,021,824 aligned logit elements equal; sequence equality 16/16 |
| Apple Clang 17 versus Homebrew Clang 23 | 16 | 320 | PASS; 387/387 teacher-forced greedy choices agree; 16/16 free-running sequences agree |
| Explicit seeded diagnostic | 1 | 10 | Expected FAIL; first generated token differs; no logit elements equal at that first aligned step |
| QEMU RVV reduction probe | 28 fixture/length pairs | 140 | Ordered matches scalar; five repeats stable; zero observed ordered/unordered output differences |

The compiler comparison uses the same host architecture, source, model and fixed inference settings. Differences are declared in the plan and recorded in the manifests. Passing these exploratory contracts does not establish equivalence for all inputs or prove that naturally occurring numerical differences never happen.

The measured smoke run took 61.62 seconds and produced 145,815,424 bytes including metadata and its report. Its simple fourfold estimate for 160 jobs was about 246 seconds and 583 MB. The actual confirmation took 280.43 seconds; the additional teacher-forced compiler comparison took 537.07 seconds. These are one-session wall times, not controlled performance measurements; local compilation and tests also ran during parts of the session.

## Diagnosis result

The declared perturbation adds 1000 to element zero of `l_out-0` at prompt position 14 for case `c001`. Fresh replay used identical token-history hashes on both sides. Layer discovery and the operator pass identified `l_out-0`, operation `ADD`, as the earliest observed differing event. The operator pass located it at event ordinal 434. Its logical payload contains 960 float32 values; one element was directly changed. The archived numerical difference reflects float32 rounding of the injected addition.

The captured replay preserved the original output discrepancy, and a second injection-off execution restored baseline logits and capture hashes. A separate test compiles the production callback against a strided tensor fixture, changes only allocation padding, and verifies that the logical payload and hash remain unchanged.

This is an injected diagnostic validation. It demonstrates the capture, shared-history, ordering and restoration machinery. It does not identify a defective compiler instruction, establish an executed RVV reduction in the native model, or complete instruction-level causality. Those mappings remain null with an explicit reason.

## Target and build findings

The freestanding QEMU probe uses RVV 1.0, VLEN 256, SEW 32, LMUL 1, round-to-nearest, unmasked input and zero seed. Lengths 0, 1, 4, 7, 8, 9 and 19 exercise empty inputs and vector tails. Static LLVM disassembly finds both reduction policies; ELF/DWARF maps them to source. Host scalar fixtures independently demonstrate non-associativity on absorption inputs. QEMU did not produce a policy difference on the tested cases, so no such difference is claimed.

The user also supplied authenticated Rostam access. A bounded one-CPU Slurm check reached the real RISC-V node `sven0`. GCC lacked vector headers; Clang compiled the probe, but the standard-vector capability test raised a caught SIGILL. No full model or broad benchmark was run there. [The exact limits and result are documented separately](rostam.md). Compatible primary-board validation and full-model RVV execution remain blocked.

A fresh native build has the same source identity and equal compared Mach-O code/data sections. Whole executable hashes differ because debug object paths and object timestamps differ; associated UUID/signature/link-edit metadata can also differ. Byte-identical executable reproduction is not claimed. Effective compile commands, cache snapshots, compiler identity and dynamic-library listings are retained for review.

## Validation and evidence

The final validation receipt records the exact passing test count and commands in `evidence/midterm/summary.json`. The completed acceptance suite has 68 passing tests with no skips, plus Ruff and native CTest. The receipt is authoritative if checks are later added. Coverage includes malformed/duplicate manifests, corruption, unsafe paths, timeouts, real-model repeatability and EOS, invalid tokens/context, ULP/zero/non-finite edge cases, aligned histories, all four verdicts, scanner aliases/stripped files, seeded restoration, strided capture and detached offline reconstruction.

Raw logits remain under `runs/` and are covered by bundle indexes. Small test receipts, build metadata, mechanism records and summary data are copied into `evidence/midterm`. `vfg verify` independently rebuilds the canonical verdict. `vfg report --offline` does the same before rendering. This is reproducibility checked by the implementing agent in this workspace, not external reproduction by another research group.

The pilot consists of 48 original prompts, eight categories, 32 exploratory cases and 16 held-out cases. It was frozen at 2026-10-01T11:11:29.693717+00:00 before candidate inspection. Only exploratory cases were executed. Margins are descriptive; no held-out canary performance or failure-prediction claim is made.

## Remaining work and submission status

Next steps are a compatible physical target/toolchain, full-model RVV execution, verified operator-to-instruction mapping, spec-aware sampled legal-tree replay with an independent implementation, canary validation on the untouched holdout, and selective hardening with controlled overhead measurements.

The README, SRS, traceability table, proposed team responsibilities and demonstration script are prepared. Mentor signatures and the prescribed meeting-record format remain external submission requirements. No meetings, reviews or signatures have been fabricated.

Mentor name: ____________________  Signature: ____________________  Date: ____________________
