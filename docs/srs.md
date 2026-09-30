# VFRED-Gate software requirements specification

Version 0.1 · mid-semester implementation · actual development date 1 October 2026

## Purpose and scope

The system determines whether the recorded observable behaviour of two explicitly declared inference stacks satisfies a user-selected compatibility contract. It preserves enough evidence to reconstruct the result offline and supports teacher-forced diagnosis through an observed layer/operator boundary.

This release implements the host/emulator software milestone. It does not determine whether a floating-point reduction tree is legally permitted by the RISC-V specification, prove an instruction caused a model discrepancy, validate predictive canaries, or search for selective hardening. These remain later project requirements.

## Actors and environment

The experiment operator chooses stacks, frozen cases, target and contract. A reviewer verifies the evidence bundle and reads the offline report. Team members maintain source, tests and documentation; mentors evaluate the signed submission separately.

Python orchestrates external C++ runner processes. The current native environment is ARM64 macOS; llama.cpp and a Q8_0 GGUF model are pinned by full revision and SHA-256. NumPy performs comparisons, Pydantic validates schemas, pyelftools reads ELF/DWARF, LLVM disassembles RISC-V ELF files, and QEMU executes the freestanding RVV mechanism probe. Slurm/SSH target discovery is recorded separately when used. No browser service, cloud account, telemetry, publication endpoint or remote Git write is part of the application.

## Functional requirements

| ID | Requirement and acceptance |
|---|---|
| FR-001 | Resolve explicit source/model/compiler/build/corpus/contract identities. Reject changed model bytes, changed binary hashes, invalid manifests and undeclared configuration differences. Archive identities with actual execution timestamps. |
| FR-002 | Execute each selected case on both stacks using fresh contexts/processes with fixed thread, context, batching, KV and greedy-decoding settings. Preserve stdout, stderr, command, environment, status, timings and repetition identity. |
| FR-003 | Inventory emitted ordered/unordered and widening RVV floating reductions in actual ELF machine code. Produce binary-hash/section-offset site IDs, available symbol and source mappings, and explicit non-applicable results for native Mach-O. Static presence never implies execution. |
| FR-004 | Independently validate token choices and compute bit equality, absolute/relative/ULP error, argmax agreement, top-k Jaccard, sequence exact match and first divergence. Restrict comparisons to aligned histories. Verify within-stack repeatability before qualification. |
| FR-005 | Evaluate every declared rule and evidence requirement. Return ERROR before INCONCLUSIVE, then FAIL or PASS. Keep legality status not_assessed. A smoke PASS cannot satisfy the 16-case contract. |
| FR-006 | Replay a shared baseline history from fresh contexts, capture logical tensor contents, locate the earliest observed difference, and validate an explicit seeded perturbation with baseline restoration. Preserve null instruction mappings where attribution has not been established. |
| FR-007 | Verify bundle hashes, sizes, completion/event counts and raw arrays offline. Recompute canonical metrics and verdict, reject inconsistencies, and generate an escaped static HTML report with raw-evidence links. |
| FR-008 | Freeze the pilot before candidate inspection, preserve disjoint case/group splits, report descriptive top-two margins, and compute progress from a fixed 100-point ledger with verified evidence. Holdouts must remain excluded from the midterm experiments. |

## Non-functional requirements

| ID | Requirement and acceptance |
|---|---|
| NFR-001 | Preserve evidence integrity. Canonical JSON forbids NaNs; duplicate keys and unsafe paths are rejected. Atomic completion metadata and SHA-256 references prevent partially written output from being accepted. |
| NFR-002 | Fail closed. Invalid tokens, oversized contexts, malformed outputs, missing bytes, interrupted jobs and tampered choices cannot silently become PASS. Timeouts or incomplete stable repetitions are INCONCLUSIVE. |
| NFR-003 | Record reproducible configuration. Build from pinned bytes in separate directories; retain effective commands/cache and remaining dynamic-library identities. Investigate fresh-build differences before claiming executable byte reproducibility. |
| NFR-004 | Bound resources. Run one model thread, use explicit timeouts and process-group termination, preflight estimated disk use, and avoid full tensor payloads in broad qualification runs. Remote jobs require scheduler limits and user-owned scratch space. |

## Interfaces and data contracts

The CLI exposes `doctor`, `validate`, `build`, `scan`, `microbench`, `corpus freeze`, `qualify`, `localise`, `verify`, `report`, and `progress`. JSON/YAML declarations use the versioned schemas in `schemas/`; unknown fields are rejected. Paths in plans resolve relative to the plan; binary/build paths resolve relative to each stack manifest.

A runner request names protocol version, mode, case, model path/hash, exact prompt tokens, context and generation budget, capture settings and optional declared diagnostic injection. Teacher forcing includes a baseline continuation. The runner accepts only `tokenize`, `free_run` and `teacher_forced`.

A completed inference output contains `result.json`, `events.jsonl`, `captures.jsonl`, and little-endian float32 `logits.f32`. Each event specifies step, history digest, chosen token and array offset. History hashes cover little-endian signed 32-bit token IDs. Capture payloads use logical tensor element order derived from shape and strides and exclude padding. Each requested output row is copied before buffer reuse.

A qualification bundle contains the resolved inputs, every request/execution/result, raw arrays, margin output, run completion and four-valued verdict, plus a `bundle.json` file index and its SHA-256 sidecar. Reports reside under an excluded `report/` directory because they are derived views. A reviewer may supply a separately trusted index hash; the sidecar alone is not an authenticity signature.

## Metric and decision semantics

Bit equality compares uint32 representations, including signed zero. Absolute and relative differences use float64 arithmetic over recorded float32 values; the relative denominator is `max(abs(baseline), epsilon)`. The monotonic ULP mapping treats both zeros as numerically identical. Non-finite values need an explicit policy and currently yield insufficient evidence.

Greedy ties choose the lowest token ID. Top-k ties use value then token ID. Free-running logit comparison includes the first differing choice and stops before histories diverge. Teacher-forced comparison requires equal histories throughout. Sequence equality includes token length and stop reason. A sequence with no observed difference is censored, not assigned a guessed divergence position. Each independent case contributes once; five repetitions check stability rather than increasing the sample count.

Qualification exit codes are 0/2/3/4 for PASS/FAIL/INCONCLUSIVE/ERROR. Missing selected IDs or invalid contracts are ERROR; missing required executions, unsupported required affinity, instability or uncontrolled manifest differences are INCONCLUSIVE. The report lists the exact evidence insufficiency and failed rules.

## Constraints and acceptance

The first model is SmolLM2-360M-Instruct Q8_0 with 49,152 vocabulary entries and 32 observed block-output boundaries. The pilot has 48 prompts in eight categories: 32 exploratory and 16 holdout. Sixteen exploratory cases form confirmation; four form smoke. Maximum prompt length is 128 tokens, context 512, generation 32, CPU threads one and KV float32.

The native compiler comparison uses Apple Clang 17 and Homebrew Clang 23, not the initially proposed GCC/Clang pair. There is no suitable local GCC toolchain for a controlled native comparison. The exact alternative and both actual compiler identities are recorded. No accuracy, legal-tree coverage, board-level qualification or general release guarantee is inferred from a passing pilot.

Run `scripts/validate.py` and `scripts/check_midterm.py` for the acceptance evidence. The traceability CSV maps requirements to checks and bundles. Results are a local self-evaluation, not independent external reproduction.

Prepared for mentor review. Mentor name: ____________________  Signature: ____________________  Date: ____________________
