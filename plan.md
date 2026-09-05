# VFRED-Gate: implementation plan for the mid-semester milestone

**Written:** 1 October 2026  
**Evaluation:** 6-7 October 2026; reporting at 09:45, evaluation from 10:00 to 13:00  
**Status:** planning only; none of the implementation tasks below is complete  
**Source:** [project synopsis](VFRED-Gate_Synopsis_Report.pdf), particularly Chapters 3-7 and Appendices A-C

## 1. What we will deliver

Build an executable vertical slice of VFRED-Gate that:

1. Records the exact model, source revision, build configuration, execution target and inputs.
2. Builds small floating-point reduction programs and inventories their emitted RISC-V instructions.
3. Runs a real SmolLM2-360M-Instruct Q8_0 model through a dedicated C++ runner.
4. Compares baseline and candidate executions against a versioned behaviour contract.
5. Returns PASS, FAIL, INCONCLUSIVE or ERROR with the corresponding exit code.
6. Replays identical token histories and identifies the earliest observed differing layer/operator in a controlled diagnostic example.
7. Preserves enough raw evidence to regenerate the verdict and a static report offline.
8. Provides an SRS draft, progress report draft, reproducible demonstration and evidence-linked completion ledger.

The intended scope is the synopsis's Phases 0-2, a bounded part of Phase 3, and the documentation needed to demonstrate them. This is a working software milestone. Answering all six research objectives remains later work.

The current repository has the synopsis PDF and an unborn Git branch. There are no existing commits, source modules, tests or measured project results to reuse. The numerical outputs printed in Appendix C are reported by the synopsis; we must rerun our own complete programs before using them as project evidence.

This request authorizes writing this plan. Implementation, dependency installation, model downloads, target execution and commits start in a subsequent implementation task.

## 2. Define 50% before implementing

Use the following **proposed engineering work breakdown**, totalling 100 points. These are planning weights, not measured research progress or an official university grading rubric. Freeze the breakdown in the first implementation milestone; do not change weights to make unfinished work count as complete.

| ID | Full-project deliverable | Total points | Planned mid-semester points | Evidence needed for the planned points |
|---|---|---:|---:|---|
| W0 | Reduction mechanism, target discovery and hardware validation | 10 | 10 | 2 host fixtures, 2 cross-compiled RVV reducers/scans, 2 emulator checks, 4 primary-board mechanism checks |
| W1 | Schemas, manifests, artifact store, build and execution infrastructure | 12 | 12 | 3 schema/manifest checks, 3 integrity/offline checks, 3 build checks, 3 local/emulated execution checks |
| W2 | ELF/DWARF instruction inventory | 6 | 6 | Actual RVV ELF inventory, source mapping, stripped-binary handling and scanner fixtures |
| W3 | Pinned model and C++ inference runner | 10 | 10 | 7 native-host real-model checks; 3 real-model RVV execution checks on a board or named emulator |
| W4 | Comparator, contract engine and four-verdict CLI | 10 | 10 | 4 metric tests, 3 verdict/evidence tests, 3 real-model end-to-end checks |
| W5 | Teacher-forced diagnosis through instruction-level causal attribution | 18 | 6 | 2 shared-history replay, 2 layer capture, 2 seeded operator-localisation checks; remaining 12 deferred |
| W6 | Canary selection and held-out failure prediction | 8 | 2 | Frozen pilot corpus, disjoint exploratory/holdout IDs and descriptive margin scores |
| W7 | Spec-aware legal-tree replay and second-implementation validation | 12 | 0 | Deferred |
| W8 | Selective hardening search, clean rebuilds and measured cost comparison | 10 | 0 | Deferred |
| W9 | Evaluation, reproducibility and project documentation | 4 | 2 | Re-derived report, SRS/progress drafts and working demonstration; final study/external reproduction deferred |
| **Total** | | **100** | **58** | Award only accepted subitems |

The target is **58/100 accepted engineering points**, leaving some margin above the requested 50%. A module existing, a mocked response, or a passing schema fixture does not establish a real-model or hardware subitem.

Track each subitem in `docs/progress.yaml` with:

- ID, fixed weight and acceptance criterion.
- Status: `not_started | implementing | validated | blocked`.
- Actual verification timestamp, source commit if one exists, test command and result.
- Evidence-bundle path and SHA-256.
- Execution class: `host | emulator | hardware | injected_test`.
- Limitations and a named reviewer when a person has actually reviewed it.

Compute progress as the sum of validated subitems. Count a subitem only once, even if it supports several research objectives.

**Hardware contingency:** absence of a primary board leaves W0's four board points unearned. Absence of real-model RVV execution leaves W3's three RVV points unearned. Completing every other planned item would yield 51/100, described explicitly as the host/emulator software milestone with hardware qualification pending. This is conditional arithmetic, not today's progress. Missing any further mandatory item can take the result below 50%.

The original synopsis requires a primary-target Phase 0 gate before later phases. If hardware is unavailable, record an ADR for a provisional host/emulator development track. That track does not pass the original physical-target gate or establish the project's hardware premise.

## 3. Scope boundaries and decisions

### Required for this milestone

- Python orchestration and a C++17 runner linked to a pinned llama.cpp revision.
- CPU inference, one sequence, one worker thread and explicit greedy selection.
- One pinned model file: SmolLM2-360M-Instruct, GGUF, Q8_0.
- FP32 single-width ordered/unordered RVV reduction microbenchmarks.
- Local execution and an emulator executor; a thin SSH executor only if a board is available and execution is authorized.
- Numeric, decision and sequence metrics; a declarative finite set of contract rules.
- Baseline-versus-itself, a controlled candidate and labelled negative diagnostic cases.
- Teacher-forced replay, selective tensor capture and seeded layer/operator localisation.
- JSON manifests/metrics, raw binary arrays, static HTML reporting and offline verification.

### Deferred

- A claim that sampled replay proves conformance or proves a defect.
- A complete instruction-level causal chain for arbitrary unmodified model builds.
- Random legal-tree generation and mixed intermediate-precision replay.
- A second physical implementation and O2/O5 cross-board conclusions.
- ddmin, beam search, automatic selective-policy generation and O4 cost conclusions.
- A validated low-cost canary suite with held-out recall guarantees.
- Task-quality and comparative-ranking contract levels.
- Distributed inference, GPU execution, multi-user services and a dashboard.
- Exhaustive ISA corner-case certification, upstream submissions and publication.

Unimplemented CLI subcommands must be absent or return an explicit unsupported error. They must never emit illustrative success output.

### Corrections to carry into the design

1. **Separate compatibility from legality.** A contract FAIL establishes incompatibility under that contract. It does not establish an ISA defect. Keep an independent `legality_status`, initially `not_assessed`.
2. **A sampled interval is not a legality oracle.** Even an interior value need not be witnessed by a sampled legal tree. A future exact replay witness supports consistency for that captured operation; a sample miss remains unresolved.
3. **Ordered instructions do not fix the whole stack.** Record chunking, product precision, FMA contraction and surrounding arithmetic. Replacing one reduction does not guarantee global bit identity.
4. **Static inventory is not execution evidence.** A disassembled reduction may never execute. Report static sites and observed dynamic calls separately.
5. **Teacher forcing equalizes token inputs, not hidden state.** Replay each stack from a fresh context; its own arithmetic may build different KV state even under the same history.
6. **No binary search for the first difference without a monotonicity proof.** Differences can disappear and reappear. Inspect ordered boundary fingerprints and refine the earliest observed differing boundary.
7. **Content addressing detects changed content when checked against a retained trusted digest.** It does not make ordinary local files physically immutable or provide external timestamp attestation.

The RVV specification describes ordered accumulation, unordered-tree latitude and a tree structure deterministic for a fixed `vtype`/`vl`. Record the scalar seed, active elements, rounding mode and instruction configuration. These are requirements for later replay, not optional metadata. [RVV 1.0 reductions](https://docs.riscv.org/reference/isa/v20260120/unpriv/v-st-ext.html#_vector_single_width_floating_point_reduction_instructions)

## 4. Prerequisites and bounded discovery

Hardware availability has not been confirmed. The plan therefore begins with discovery, without assuming a board, credentials or an existing Linux toolchain.

| Item | How to resolve it | Output | If unavailable |
|---|---|---|---|
| Native host | Record OS, architecture, RAM, free disk and installed build tools | `environment/host.json` | Install only needed dependencies during implementation |
| Linux RV64 build environment | Prefer an available Linux host/container/VM; cross-compile from a recorded environment | Toolchain manifest, sysroot hash | Continue native work; mark RVV build checks blocked |
| GCC/Clang | Capture full versions, executable hashes, target triple and sysroot; compile an intrinsic probe | `toolchains/*.json` | Use one working compiler first; two-compiler study remains pending |
| RVV emulator | Pin emulator version, guest/user-mode choice, CPU options and actual V support probe | `targets/rvv-emulator.json` | Do not substitute host execution for an RVV result |
| Primary board | Obtain model/ISA details and permitted access method; run the probe in a user-owned directory | `targets/rvv-primary.json` | Keep physical gate blocked; use provisional emulator track |
| llama.cpp | Select one full commit SHA; compile the API probe below | `third_party/llama.lock.json` | Resolve API mismatch before writing the full runner |
| Model | Resolve repository revision and exact Q8_0 filename, download once, compute full SHA-256 | `models/model.lock.json` | No real-model milestone credit |
| Scope ownership | Confirm proposed team responsibilities | `docs/responsibilities.md` | Keep assignments labelled proposed |

Set a discovery budget of one focused implementation session. At its end, list which environments are usable and which gates are blocked. Do not spend the entire remaining preparation window provisioning a second board.

The model repository advertises Q8_0, but the exact artifact name and digest are deliberately unresolved here. Resolve them rather than copying the synopsis's abbreviated example hash. [Official model repository](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF/tree/main)

QEMU is an execution fallback; its reported configuration must be preserved. Different emulator CPU settings are not evidence from two independent hardware implementations. [QEMU RISC-V documentation](https://www.qemu.org/docs/master/system/target-riscv.html)

## 5. Planned repository structure

Create only modules required by the milestone. The following paths are implementation targets, not files that already exist.

~~~text
plan.md
README.md
pyproject.toml
uv.lock
CMakeLists.txt
CMakePresets.json
cmake/toolchains/rv64-linux.cmake
src/vfg/
  cli.py
  errors.py
  schema.py
  manifest.py
  controller.py
  build.py
  store.py
  scan/elf.py
  scan/disassembly.py
  scan/sites.py
  execute/base.py
  execute/local.py
  execute/emulator.py
  execute/ssh.py                  # only if required by available board
  compare/alignment.py
  compare/numeric.py
  compare/decision.py
  compare/sequence.py
  contracts/engine.py
  canary/corpus.py
  canary/margins.py
  localise/replay.py
  localise/boundaries.py
  report/render.py
  report/templates/report.html
runner/
  CMakeLists.txt
  src/main.cpp
  src/protocol.cpp
  src/model_session.cpp
  src/tokenize.cpp
  src/generate.cpp
  src/replay.cpp
  src/capture.cpp
  src/test_injection.cpp
  include/vfg/*.hpp
microbench/
  CMakeLists.txt
  src/fixtures.cpp
  src/scalar.cpp
  src/rvv_ordered.cpp
  src/rvv_unordered.cpp
  src/main.cpp
schemas/
  stack.schema.json
  target.schema.json
  model.schema.json
  corpus.schema.json
  plan.schema.json
  contract.schema.json
  run.schema.json
  verdict.schema.json
contracts/
  self-check.yaml
  pilot-decision.yaml
plans/
  self-check.yaml
  native-comparison.yaml
  seeded-localisation.yaml
corpora/
  source/pilot.jsonl
  frozen/pilot.tokens.jsonl
  splits/pilot.json
third_party/
  llama.lock.json
  patches/                       # only patches actually needed
tests/
  unit/
  integration/
  acceptance/
  fixtures/
scripts/
  check_midterm.py
  demo_midterm.sh
docs/
  adr/
  api-map.md
  srs.md
  midterm-report.md
  requirements-traceability.csv
  responsibilities.md
  progress.yaml
  demo.md
prereg/
  pilot-v1.md
~~~

Ignore `build/`, `.venv/`, `models/*.gguf`, `runs/`, `artifacts/` and downloaded `third_party/llama.cpp/`. Track lock metadata, small deterministic test inputs and scripts. Keep large evidence bundles locally with a manifest; do not add model weights to Git.

Use Python 3.11+, CMake and a C++17 compiler. Initial Python dependencies: Typer, Pydantic, PyYAML, NumPy, pyelftools and Jinja2; development dependencies: pytest and Ruff. Pin resolved versions in `uv.lock`. Export strict JSON Schemas from the Pydantic definitions and check that exported schemas remain in sync. Do not maintain two independent schema implementations.

Use JSON/JSONL plus raw arrays initially. Defer Parquet and heavy statistics packages until table volume or confirmatory analyses justify them.

## 6. Stable data contracts

### 6.1 Manifest and identity rules

Every schema has `schema_version`. Reject unknown keys in executable plans and contracts, duplicate YAML keys, non-finite numeric thresholds and invalid SHA strings. Parse YAML safely. Never evaluate threshold expressions with `eval`.

Resolve relative paths against the plan file's directory, then expand them into a resolved execution plan. Hash canonical UTF-8 JSON: sorted object keys, fixed separators, no NaN/Infinity and no self-referential digest fields. Hash files by their raw bytes. Keep identity fields separate from observational fields such as timestamps.

| Record | Required contents |
|---|---|
| Stack | Source revision; patch digest; compiler/linker identities; command argument arrays; environment allowlist; CMake cache digest; target triple; sysroot; FP flags; binary/library digests; reduction policy; build class |
| Target | Architecture; OS/kernel; hardware/emulator classification; ISA probe result; VLEN where observed; CPU selection; affinity support/result; emulator command; memory limits |
| Model | Repository/revision; exact filename; file SHA-256; quantisation; vocab size; tokenizer/template metadata digests |
| Corpus | Case ID; source/group ID; frozen token IDs; tokenization settings; model/tokenizer digest; split; maximum generation length |
| Run | Run ID; actual times; input identity hashes; executable identity; all cases/repetitions; completion state; outputs; exclusions; errors; execution class |
| Verdict | Contract digest; rule results and counts; evidence validation; verdict/exit code; reasons; legality status; reportable limitations |
| Capture | Case/repetition; decode step; input-history hash; graph event ordinal; tensor name/op; shape/dtype/strides; layer mapping; byte digest; optional payload reference |

A run ID identifies an execution. It is not just the input hash: repeated executions with the same inputs require distinct run records.

### 6.2 Runner protocol

Use one JSON request file per case/repetition and one dedicated output directory. A request contains:

- Protocol version, case ID, model path and expected model digest.
- Mode: `free_run`, `teacher_forced` or `tokenize`.
- Frozen prompt token IDs, optional forced continuation and capture selection.
- Context length, token budget, thread counts, batch/microbatch settings and explicit CPU configuration.
- Output paths and optional diagnostic injection settings.

The runner writes an atomic `result.json`, an ordered `events.jsonl` and little-endian binary arrays with sidecar metadata. Log human-readable diagnostics to stderr. Python reads result files, never terminal prose.

Use little-endian float32 for logits, explicit shape and byte count, and an array checksum. Keep uint32 bit views for bit equality. Do not round logits through decimal JSON. An event points to the relevant array offset.

An interrupted output directory remains incomplete and cannot be reused as a completed run.

### 6.3 Example behaviour contract to implement

This is a proposed development contract, not a validated release guarantee:

~~~yaml
schema_version: 1
id: pilot-decision-v1
compatibility_level: decision
rules:
  - id: token_choice
    metric: argmax_agreement_rate
    alignment: teacher_forced_baseline
    operator: ge
    threshold: 1.0
  - id: complete_sequence
    metric: sequence_exact_match_rate
    alignment: free_run
    operator: ge
    threshold: 1.0
evidence:
  repetitions: 5
  minimum_cases: 16
  stability: bitwise_within_stack
  require_all_cases: true
  unexpected_manifest_differences: reject
on_insufficient_evidence: INCONCLUSIVE
~~~

A separate self-check contract requires bit equality. Define a four-case, five-repetition `smoke-self-check-v1` for quick checks and a sixteen-case, five-repetition `confirmation-self-check-v1` for acceptance. A smoke PASS does not satisfy the confirmation contract or earn the real-model qualification acceptance points. Permit only explicitly implemented metrics and alignments; reject unsupported task/ranking levels. Keep exploratory thresholds separate from future confirmatory contracts.

### 6.4 Internal interfaces

Implement these boundaries before connecting the controller. The names below describe planned Python interfaces; use typed records rather than unstructured dictionaries between modules.

~~~python
resolve_plan(path: Path) -> ResolvedPlan
diff_manifests(baseline: StackManifest, candidate: StackManifest,
               allowed: ExperimentChanges) -> ManifestDiff
build_stack(stack: StackManifest) -> BuildResult
scan_binary(binary: Path, tools: ToolchainManifest) -> InstructionInventory
execute(request: RunRequest, target: TargetManifest) -> ExecutionResult
validate_evidence(run: RunBundle) -> EvidenceAssessment
align_outputs(baseline: RunBundle, candidate: RunBundle,
              mode: AlignmentMode) -> AlignedCases
compute_metrics(cases: AlignedCases, rules: list[Rule]) -> MetricResults
evaluate_contract(contract: Contract, evidence: EvidenceAssessment,
                  metrics: MetricResults) -> Verdict
localise(replays: ReplayPair, capture: CapturePlan) -> LocalisationResult
verify_bundle(path: Path) -> VerificationResult
render_report(bundle: VerifiedBundle, output: Path) -> Path
~~~

The runner is an external process behind `execute`; numerical comparisons must not depend on a Python binding to llama.cpp. Use a fixture executor in unit tests and the real executable in integration/acceptance tests. Executor fixtures never earn runtime or hardware points.

## 7. Milestone M0: establish the reduction mechanism

**Dependencies:** compiler/target discovery.  
**Files:** `microbench/`, target/toolchain manifests, `tests/fixtures/reductions/`.  
**Credits:** W0; scanner output also supplies inputs for M3.

### Implementation

1. Create scalar FP32 left-fold, pairwise-tree and FP64-accumulating reference reducers.
2. Use exact hexadecimal inputs or a specified integer PRNG with saved input bytes. Do not use platform-dependent `rand()` sequences as cross-platform evidence.
3. Compile scalar references with reassociation and contraction disabled. Inspect the generated code so optimisation has not silently changed the intended reference.
4. Implement explicit ordered and unordered RVV intrinsic wrappers. The intrinsic compiler interface is available through `riscv_vector.h`; verify the installed compiler's supported version with a compile probe. [GCC RVV intrinsic documentation](https://gcc.gnu.org/onlinedocs/gcc/RISC-V-Vector-Intrinsics.html)
5. Start with unmasked FP32, SEW=32, LMUL=1, RNE, explicit scalar seed and finite inputs. Capture input bytes, output bits, `vl`, `vtype`, rounding mode and exception flags.
6. Implement strip-mining that carries the scalar accumulator across chunks. Record the actual chunk sequence; a per-instruction result and a whole-array result must be distinguishable.
7. Include arrays around VLMAX: length 1, VLMAX-1, VLMAX, VLMAX+1 and 2*VLMAX+3, deduplicating invalid lengths. Handle n=0 by returning the seed and mark that no reduction instruction executed.
8. Include cancellation, absorption, mixed magnitudes, all-positive sums and signed-zero fixtures. Test a simple exact case such as 1+2+3+4 independently of the adversarial cases.
9. Execute on the host, named emulator and primary board when available. Use five repetitions for each target/input/policy combination.
10. Archive build logs, disassembly, executable SHA, source input hashes, per-instruction metadata and outputs.

A deterministic cancellation fixture may use the exactly representable values `[16777216, 1, -16777216, 1]`. Establish the actual left-fold/tree outputs in tests. Do not assume a target's unordered implementation uses our pairwise tree.

### Gate G0

- The scalar and vector ordered paths agree on finite-input cases when they perform the same sequence and rounding.
- The ELF contains the requested ordered/unordered instructions in the intended wrapper functions.
- At least one host fixture demonstrates non-associativity.
- The emulator actually executes the vector wrappers.
- For the original physical-target gate: the primary board exhibits a reproducible difference between the declared policies, with the relevant instructions identified.
- A board whose unordered instruction matches ordered output is a valid possible result. It earns execution evidence but does not satisfy the original divergence gate; record the negative result and bounded search.
- Allocate at most two focused sessions to expanding the deterministic input corpus after a no-divergence result. Do not silently substitute an injected result.

## 8. Milestone M1: schemas, environment locks and artifact storage

**Dependencies:** initial discovery; can proceed on the provisional host track.  
**Files:** `schema.py`, `manifest.py`, `store.py`, schemas, lock files and tests.  
**Credits:** first six points of W1.

### Implementation

1. Implement strict manifest schemas and validation errors with a field path and reason.
2. Add `vfg doctor` to inventory tools without installing or changing them. Separate `available`, `missing` and `not_probed`.
3. Add manifest comparison with three classifications: unchanged, planned experimental difference and uncontrolled difference.
4. A planned compiler change permits its derived compiler identity, build commands and binary hashes to differ. It does not permit the model, corpus, unrelated runtime patches or sampling settings to change.
5. Store artifacts under `artifacts/sha256/<first-two>/<remaining-digest>`. Write a temporary file, hash it, then atomically promote it; verify an existing object before reuse.
6. Store per-run manifests under `runs/<run-id>/`, with an object list covering every input/output referenced by the verdict.
7. Implement `vfg verify` to verify referenced bytes, sizes, schemas, required event counts and completion markers.
8. Recompute metrics from archived raw outputs in `vfg report --offline`. Do not merely reformat saved metric totals.

### Gate G1a

- Changing one model byte changes its digest and prevents reuse.
- Changing an unplanned setting yields INCONCLUSIVE before comparison.
- Changing an allowed compiler identity does not accidentally mask an unrelated change.
- A corrupted artifact or truncated result is detected.
- A bundle copied to a new directory produces the same canonical metrics/verdict without the original build directory, model file or execution target, provided all comparison outputs are present.
- Integrity failures cannot produce PASS.

## 9. Milestone M2: reproducible builds and controlled execution

**Dependencies:** M1 and an available compiler environment.  
**Files:** `build.py`, executor modules, CMake configuration, lock metadata.  
**Credits:** remaining six points of W1.

### Build steps

1. Resolve a full llama.cpp commit and save the archive/checkout digest. Do not build from a moving branch.
2. Build a minimal probe against that checkout that loads the model, processes token IDs, obtains logits and registers an evaluation callback.
3. Write `docs/api-map.md` with the pinned symbols, source locations, CMake options and probe result.
4. Link a static llama/ggml build into the runner where supported. Record all remaining dynamic runtime libraries and the loader/sysroot.
5. Use separate native and RV64 build directories. Initial controlled compiler flags: `-O2 -g -fno-fast-math -ffp-contract=off`. For the RV64 Linux probe, start with `-march=rv64gcv -mabi=lp64d` after checking target support and the sysroot ABI. Disable implicit host-native tuning for portable cross-target builds. Compile strict scalar references separately with the compiler's verified vectorisation-disable flags; explicit RVV wrappers remain in separate translation units. Save all effective flags rather than assuming the top-level flags override upstream settings.
6. Disable GPU/Metal/CUDA/Vulkan, BLAS/Accelerate offload and unwanted threading through options verified in the pinned checkout. Treat an unused CMake variable warning as an unresolved configuration error.
7. Record generated compile commands, link commands, CMake cache, executable hash and all source/patch hashes.
8. Verify the locked build procedure from a fresh build directory. Compare resulting binary hashes; if they differ, identify path/time/build-ID inputs before claiming byte reproducibility.

Candidate dimensions for the initial comparisons:

| Comparison | Baseline | Candidate | Purpose |
|---|---|---|---|
| Self-check | One binary/configuration | The same binary/configuration, fresh processes | Stability and comparator control |
| Compiler exploration | Pinned GCC build | Pinned Clang build, otherwise identical target/settings | Descriptive code-generation comparison |
| Policy mechanism | Explicit ordered wrapper | Explicit unordered wrapper | Reduction mechanism test |
| Seeded diagnosis | Instrumented runner with injection off | Same diagnostic build with declared injection on | Validate diagnosis; never hardware-defect evidence |

Do not compare different native host architectures and call the result a compiler-only experiment.

### Execution steps

- Invoke subprocesses with argument arrays, an explicit working directory and an environment allowlist.
- Capture stdout, stderr, start/end times, return status, timeout and the complete command.
- Use a fresh context/process per case/repetition; model load time is recorded separately.
- Pin one core on Linux when supported and record whether it succeeded. An unsupported affinity setting must be visible in the target profile.
- Stop after the configured timeout; keep partial artifacts and classify missing evidence.
- An emulator executor wraps the same runner protocol and records emulator/sysroot identities.
- If needed, the SSH executor stages only named assets in an authorized user-owned directory, verifies remote hashes, invokes the runner and retrieves the bundle. No privileged system changes or global cleanup.

### Gate G1b

A locked stack can be built, scanned and executed from its manifest. Timeout, missing executable, nonzero exit and truncated JSON cases have explicit outcomes. Native/emulator outputs preserve their execution class.

## 10. Milestone M3: emitted-instruction inventory

**Dependencies:** M0 binaries and M1 artifact storage.  
**Files:** `scan/`, real ELF fixtures and scanner tests.  
**Credits:** W2.

### Implementation

1. Verify ELF class, endianness and machine architecture before decoding.
2. Run a recorded RISC-V-capable objdump with disassembly, symbols and line information. Retain its raw output.
3. Use pyelftools for build IDs, sections, symbol bounds and DWARF line tables.
4. Recognise `vfredosum.vs`, `vfredusum.vs`, `vfwredosum.vs` and `vfwredusum.vs`; normalise documented older assembler aliases.
5. Emit one site record per instruction: binary hash, section, address, instruction bytes, mnemonic, operands, symbol, optional file/line and mapping status.
6. Use `binary_sha256 + section + instruction_offset` as the exact static identity. Source file/line is a human correlation field, not a globally stable instruction ID.
7. Account for load bias when comparing runtime PCs to PIE/shared-object offsets.
8. Preserve multiple inline/source candidates rather than guessing one.
9. An ELF with zero reductions produces an explicit zero inventory. A non-RISC-V native runner produces `not_applicable`.
10. Missing DWARF degrades to address/symbol mapping, with no invented line number.

### Gate G2

Tests use real compiled fixtures containing zero, one and multiple reduction sites, a stripped variant, malformed ELF and a non-RISC-V binary. A changed binary must not reuse the previous site's address identity. The report clearly separates inventory from dynamic execution.

## 11. Milestone M4: real-model C++ runner

**Dependencies:** API probe, locked model, M1-M2.  
**Files:** `runner/`, model metadata, tokenization tests and native integration tests.  
**Credits:** W3.

### 11.1 API and build choices

The public header currently exposes token batches, model/context setup and logit access. Build the probe around the API at the selected commit; keep upstream calls inside `model_session.cpp`. The legacy `llama_decode`/`llama_get_logits_ith` route is a candidate, not a promised interface for an unselected revision. [llama.cpp public API](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/include/llama.h)

Use the upstream simple example only to check setup and cleanup patterns; its defaults are not the qualification profile. [Upstream simple example](https://github.com/ggml-org/llama.cpp/blob/master/examples/simple/simple.cpp)

### 11.2 Fixed pilot configuration

| Setting | Initial value |
|---|---|
| Model | Exact locked SmolLM2-360M-Instruct Q8_0 file |
| Backend | CPU only; verify backend assignment |
| Sequences / worker threads | 1 / 1 for both prefill and decode |
| Context | 512 tokens |
| Prompt limit | 128 tokens including special tokens |
| Generated tokens | At most 32; EOS stops generation |
| Prefill batch/microbatch | 1 / 1 initially, matching the simple isolation profile |
| Repetitions | 5 fresh processes per case and stack |
| Greedy tie rule | Highest logit, then lowest token ID on exact ties |
| KV representation | Explicitly selected and recorded from the pinned API |
| Additional samplers | None; no penalties, temperature sampling or top-p |
| NaN logits | Invalid numerical evidence; explicit reason and no silent argmax |
| Context overflow | Reject input before inference |

These values are pilot defaults. If runtime cost forces a change, freeze a new plan/contract version before the affected run and keep earlier results distinct.

### 11.3 Tokenization and generation

1. Resolve the chat template once, record its exact text/digest and format the pilot prompts consistently.
2. Tokenize with the locked model's tokenizer. Store integer IDs and special-token settings in the frozen corpus.
3. Validate token IDs against the vocabulary and confirm prompt+generation fits context.
4. Load the model, initialise a fresh context and ingest the prompt in the declared batch schedule.
5. Capture the final prompt logits as generation step zero: they predict the first continuation token.
6. Select the token with the declared tie rule, save its ID and append it for the next decode step.
7. Record EOS as a selected token/event before stopping. Keep the stop reason distinct from token-budget exhaustion.
8. Copy each logit vector before the next decode call can reuse its buffer.
9. Save full logits for the small confirmation suite. A later screening profile can save top-k and digests, but must mark full numeric metrics unavailable.
10. Record model load, prefill and generation timings separately. These instrumented times are diagnostics, not O4 performance evidence.

### Gate G3

- A real GGUF generates actual token sequences from frozen IDs.
- Five self-runs have matching output bits under the declared stability requirement, or the instability is reported and blocks the contract verdict.
- Python independently recomputes selected tokens from archived logits and matches the runner.
- EOS, token budget, exact ties, invalid tokens and context overflow are tested.
- Changing JSON whitespace cannot change frozen token inputs.
- The same runner protocol works on RVV when available. A host run does not earn the RVV subitem.

## 12. Milestone M5: comparison and four-valued qualification

**Dependencies:** M1, M4; small fixtures can be implemented earlier.  
**Files:** comparator modules, contract engine, controller and CLI.  
**Credits:** W4.

### 12.1 Alignment rules

Maintain two explicit comparison modes:

- **Free run:** compare generated sequences and first divergence. Compare same-history logits only through the first differing selection; later free-run logits are labelled different-history outputs.
- **Teacher-forced baseline:** both stacks ingest the prompt and the same baseline continuation, using fresh independent contexts. Compare next-token logits at each identical history.

Do not mix these populations under one agreement rate. Store case ID, step and history hash in every aligned row. A missing row is missing evidence, not agreement.

### 12.2 Metric definitions

| Metric | Exact implementation |
|---|---|
| Bit equality | Compare canonical array dtype/shape and raw element bits; signed zeros remain distinct |
| Max absolute error | Maximum of abs(candidate-baseline) over aligned finite values, differences calculated in float64 |
| Max relative error | abs(candidate-baseline) / max(abs(baseline), declared epsilon); epsilon saved in contract |
| FP32 ULP distance | Monotonic integer mapping of finite float32 values; coalesce signed zero only for this numeric metric |
| Argmax agreement | Matching selected token IDs / number of eligible aligned history steps |
| Top-k overlap | Jaccard of token-ID sets, ordering by descending logit then ascending ID for ties |
| Sequence exact match | Matching full token sequence including termination behaviour / stable complete cases |
| First divergence | First unequal token position; shorter unequal termination also counts; no divergence is right-censored |
| Top-two margin | Highest logit minus second-highest, attached to stack/case/step; descriptive sensitivity only |

Equal same-sign infinities may count as equal under an explicit rule; unmatched infinities and NaNs must be surfaced without computing misleading finite averages. Save exceptional counts.

Report numerators, denominators, excluded cases and reasons. Five repetitions establish stability; they do not multiply the number of independent prompts by five. Token steps within a prompt are dependent, so do not present a naive token-level confidence interval as a generalisation guarantee.

### 12.3 Verdict precedence and exit codes

| Order | Condition | Verdict | Exit |
|---:|---|---|---:|
| 1 | Invalid executable configuration, unsupported metric, internal tool/protocol error or corrupt bundle | ERROR | 4 |
| 2 | Missing required evidence, timeout, unstable case, unsupported isolation requirement or uncontrolled difference | INCONCLUSIVE | 3 |
| 3 | Complete stable evidence and at least one rule fails | FAIL | 2 |
| 4 | Complete stable evidence and every rule passes | PASS | 0 |

This conservative order means a partially failing but incomplete run stays INCONCLUSIVE at the top level; retain the observed rule failures in the evidence. A runner crash is recorded as an execution error with its stderr/exit, not inferred to be an ISA defect.

`legality_status: not_assessed` remains independent of all four verdicts in this milestone.

### Controller state machine

~~~text
validate plan
  -> resolve and hash inputs
  -> verify allowed differences
  -> build or verify locked binaries
  -> scan
  -> execute all required case/repetition jobs
  -> validate completeness and stability
  -> align outputs
  -> compute metrics
  -> evaluate rules
  -> seal evidence manifest
  -> render report
~~~

Each stage records status and artifacts. Resume only from verified completed artifacts whose input identities still match. Never count incomplete jobs as cache hits.

### Gate G4

- Self-comparison returns PASS and exit 0 from real model outputs.
- A labelled altered-logit fixture returns FAIL and exit 2.
- Missing repetitions, an unstable fixture and an unplanned manifest difference return INCONCLUSIVE and exit 3.
- Invalid rules and corrupt artifacts return ERROR and exit 4.
- Recomputing from raw artifacts reproduces the same metric counts and verdict.
- A real compiler/policy comparison reports whatever it observes. A natural token flip is desirable evidence, not a required result to fabricate.

## 13. Milestone M6: teacher forcing and bounded localisation

**Dependencies:** M4-M5.  
**Files:** runner replay/capture, `localise/`, diagnostic fixtures and capture manifest.  
**Credits:** six of W5's eighteen points.

### 13.1 Replay

1. Find the first free-run token disagreement at zero-based continuation position j.
2. Save the prompt and the agreed continuation before j, along with hashes.
3. Restart both stacks from empty contexts and replay that identical history.
4. Capture the logits predicting token j; confirm that the diagnostic replay preserves the observed discrepancy.
5. For latent divergence, replay and capture earlier prefill/decode boundaries as well. Do not begin inspection only after j.
6. For a full aligned decision test beyond j, teacher-force the baseline continuation into both stacks and label that separate from free-running behaviour.
7. Verify matching history hashes before comparing internal captures. Never copy one stack's KV cache into the other.

### 13.2 Capture

Use the scheduler evaluation callback when it exposes the required tensors at the pinned revision. During its query phase, select nodes; during observation, copy/hash the completed tensor before reuse. [ggml callback interface](https://github.com/ggml-org/llama.cpp/blob/master/ggml/include/ggml-backend.h)

Capture two tiers:

- Tier 1: ordered boundary events with tensor metadata and SHA-256, covering the model's observed block outputs and final logits.
- Tier 2: full tensor payloads for operators within the earliest observed differing block and at the selected diagnostic site.

Discover actual tensor names and graph order from the pinned model. Save a model-specific layer map. Do not assume the illustrative `blk.14.ffn_norm` name in the synopsis exists unchanged.

Canonicalize logical tensor element order using shape/strides. Do not hash padding or assume every view is contiguous. Check that capture-enabled and capture-disabled runs yield the same model outputs for the tested corpus. If callback selection changes execution/fusion enough to alter numerics, record that and diagnose only within matched instrumented builds.

### 13.3 Diagnostic example

Implement a test-only perturbation at one explicitly selected tensor event, applied in a bounded local patch if the callback cannot safely provide that intervention.

- Select one case, layer/operator, element and deterministic perturbation.
- Record the injected delta and exact event in the run manifest.
- Compile injection support only in a diagnostic build.
- Run injection off, injection on and injection off again.
- Require the localisation procedure to identify the seeded layer/operator and the on/off effect to be reproducible.
- A sufficiently strong test perturbation may produce a visible token change. Its magnitude is a test fixture, not a naturally occurring rounding error.
- If only tensor or logit differences are produced, report that exact scope.

This validates the diagnostic plumbing. It does not complete instruction-level causal attribution or show that a compiler emitted a defective instruction.

### 13.4 Optional reduction-specific intervention

After the mandatory work passes, inspect the actual executed RMSNorm or another observed floating-point reduction. The current CPU RMSNorm source uses an accumulation loop and also has fused variants, so a fixed FP32 `vfredusum` site cannot be assumed. Verify types, fusion, dispatch and emitted instructions at the pinned revision. [CPU operator source](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/ggml/src/ggml-cpu/ops.cpp)

A controlled reduction patch must preserve product computation and surrounding operations while varying a declared accumulation policy. Record any change in accumulation precision separately. A deliberately modified FP32 variant of a wider native accumulator is a controlled experiment, not an unchanged native runtime.

If a trustworthy operator-to-instruction map cannot be established, stop at verified layer/operator localisation.

### Gate G5

- Both replay executions have identical token-history hashes.
- Layer/event ordering is reproducible and matched by explicit keys.
- A seeded perturbation is located at the expected layer/operator.
- Removing the perturbation restores the self-check result.
- The report labels the result as an injected diagnostic validation.
- Unmapped source/instruction fields remain null with a reason.

## 14. Milestone M7: pilot corpus and repeatable evaluation

**Dependencies:** M4 and metric code.  
**Files:** `corpora/`, `canary/`, `prereg/pilot-v1.md`.  
**Credits:** two points of W6.

1. Write 48 short, non-sensitive prompts, grouped into eight categories with six prompts each: arithmetic, factual completion, constrained formatting, short code, reasoning, ambiguous continuation, punctuation/Unicode and ordinary conversation.
2. Assign permanent case/group IDs. Avoid near-duplicate prompts crossing the split.
3. Freeze 32 exploratory prompts and 16 held-out pilot prompts before looking at candidate differences; save the split and its digest.
4. Tokenize once with the locked model/template; verify every prompt fits 128 tokens.
5. Use four exploratory cases for quick build checks.
6. Use a fixed 16-case exploratory confirmation subset for the mandatory midterm demonstration.
7. For each baseline/candidate pair, run 16 cases x 2 stacks x 5 repetitions = 160 case executions, each generating at most 32 tokens: at most 5,120 generated tokens, plus repeated prefill.
8. Use the remaining exploratory cases to examine top-two margins when time permits.
9. Keep the held-out 16 cases sealed for later canary validation. If used for an early descriptive check, record that it is no longer an untouched holdout.
10. Persist all exclusions and unstable cases. The default complete-corpus contract becomes INCONCLUSIVE if a required case is missing or quarantined.

Write the actual freeze timestamp, not a reconstructed September date. Distinguish this pilot plan from the later confirmatory preregistration.

At the end of the first four-case real-model run, measure wall time and artifact bytes. Estimate the 160-run cost from those observations. Example planning formula: model-load cost per run + prefill cost per run + decode cost per generated token. Do not insert an assumed tokens/second figure.

Full float32 logit storage is approximately `4 * vocab_size * captured_steps` bytes, before metadata. Read vocabulary size from the model. Check disk capacity before capturing every layer. If the run is too expensive, reduce diagnostic captures first; any corpus/repetition change requires a new contract and cannot be described as passing the old one.

### Gate G6

Frozen IDs, model/tokenizer hashes, split manifests and descriptive margin outputs reproduce exactly. Do not claim O1's canary recall/cost objective from this pilot.

## 15. Milestone M8: report, SRS and demonstration package

**Dependencies:** accepted results from M0-M7.  
**Files:** report renderer, README, SRS, midterm report, traceability map and demo script.  
**Credits:** two points of W9.

### Static report contents

- Run identity, actual timestamp and execution class.
- Model, stack and target digests.
- Declared and uncontrolled differences.
- Completion/stability counts and exclusions.
- Contract rules, denominators, observed metrics and verdict.
- Static RVV inventory with mapping confidence.
- First divergence and teacher-forced alignment details.
- Localisation evidence and injection labels where applicable.
- Missing capabilities and hardware-dependent limitations.
- Links to local raw artifacts and the verification command.

Use local HTML/CSS, no CDN resources and no server requirement. Escape prompt text, tool output and filenames. Plot only recorded data; a sequence without divergence is shown as censored rather than assigned an invented failure position.

### Documentation

`docs/srs.md` should contain purpose, scope, actors, environment, external interfaces, numbered functional/non-functional requirements, data contracts, error cases, constraints and acceptance methods.

`docs/requirements-traceability.csv` maps each requirement to module, test, evidence bundle and current status. Initial requirement IDs:

| ID | Requirement | Principal acceptance check |
|---|---|---|
| FR-001 | Verify model/source/build/input identities | Changed model byte rejected |
| FR-002 | Run declared baseline/candidate configurations | Actual runner request/result pair |
| FR-003 | Inventory emitted RVV reductions | Real compiled ELF fixture |
| FR-004 | Measure stable comparable outputs | Five repetitions and alignment checks |
| FR-005 | Evaluate versioned behaviour contracts | Four verdict/exit checks |
| FR-006 | Replay identical token histories | History-hash equality |
| FR-007 | Localise an observed layer/operator difference | Seeded on/off diagnostic |
| FR-008 | Re-derive evidence offline | Detached bundle regeneration |
| NFR-001 | Keep qualification assets local | Offline report with local assets |
| NFR-002 | Detect incomplete/corrupt evidence | Truncation/hash tests |
| NFR-003 | Make configuration reproducible | Locked fresh-directory build |
| NFR-004 | Bound execution/storage use | Timeout and measured budget checks |

`docs/midterm-report.md` should explain what was implemented, actual results, limitations, weighted progress and the remaining work. Use the synopsis as background; do not change proposed results into completed claims.

Provide mentor-signature spaces in later printable report/SRS artifacts. Only a real mentor can supply the signatures. A meeting-record template must wait for the prescribed format or be explicitly provisional; populate it only with actual meetings. Drafts are counted as software documentation; signed submission readiness remains a separate checklist.

The screenshot does not explicitly require slides. Prepare a short walkthrough script now; create slides only if needed by the evaluation instructions.

### Gate G7

A second run of offline report generation reproduces canonical metrics and verdict. A person can follow the README in a clean environment and execute the demo. Record which parts have actually been independently exercised; do not label self-checks as external reproduction.

## 16. CLI specification and demonstration commands

Every command below is an **interface to implement**. None exists yet. Return code 0 from a report/verify operation means that operation succeeded; the saved qualification verdict can still be FAIL.

~~~text
vfg doctor --output environment/host.json
vfg validate --plan plans/self-check.yaml
vfg microbench --target targets/rvv-emulator.json --output runs/mechanism
vfg build --stack stacks/baseline.yaml
vfg scan --binary build/rvv/vfg-microbench --output runs/inventory.json
vfg corpus freeze --source corpora/source/pilot.jsonl --model models/model.lock.json
vfg qualify --plan plans/self-check.yaml --output runs/self-check
vfg qualify --plan plans/native-comparison.yaml --output runs/comparison
vfg localise --qualification runs/comparison --case CASE_ID --capture layer
vfg localise --qualification runs/seeded --case CASE_ID --capture operator
vfg verify --run runs/comparison
vfg report --run runs/comparison --offline --output runs/comparison/report
vfg progress --ledger docs/progress.yaml
~~~

Add `stacks/baseline.yaml`, `stacks/candidate.yaml` and target/model lock files during their corresponding milestones. Make `plans/self-check.yaml` use the sixteen-case confirmation contract; put the four-case demo in `plans/smoke-self-check.yaml` so their results cannot be confused.

The controller may call lower-level commands internally; avoid duplicate implementations. Invalid CLI usage follows the documented ERROR=4 policy for qualification commands rather than an accidental framework exit-code default.

`scripts/demo_midterm.sh` must demonstrate:

1. Doctor and locked-input validation.
2. Reduction fixture execution and actual disassembly.
3. A small real-model self-check returning PASS.
4. A labelled failing fixture returning FAIL.
5. Missing evidence returning INCONCLUSIVE.
6. Invalid input returning ERROR.
7. Shared-history replay and seeded localisation.
8. Offline verification and report regeneration.
9. The evidence-derived progress total and blocked items.

Use isolated output directories for negative cases. Never corrupt the only retained successful evidence bundle. If hardware is unavailable during presentation, identify archived hardware evidence as archived and show its hashes; do not imply it is a live run.

## 17. Test matrix

Tests below protect the numerical and evidence claims. Avoid adding tests that merely mirror file layout or repeat library behaviour.

| Layer | Required cases | Gate |
|---|---|---|
| Reduction references | Exact sum, cancellation, absorption, irregular lengths, recorded seeds | G0 |
| RVV execution | Actual ordered/unordered instructions, active VL, repeatability, tail lengths | G0 |
| Schema/manifest | Unknown/duplicate keys, invalid hash, allowed/forbidden difference | G1a |
| Artifact store | Round trip, collision-path validation, corruption, interrupted write | G1a |
| Executor | Timeout, missing program, child error, partial output, argument preservation | G1b |
| ELF scanner | Zero/multiple sites, aliases, stripped debug info, invalid ELF | G2 |
| Runner | Real model, EOS, context limit, ties, invalid tokens, copied logits | G3 |
| Numeric comparator | Adjacent floats, negative floats, zeros, NaNs/infinities, shape mismatch | G4 |
| Alignment | Same history, first divergence, missing step, different stop lengths | G4 |
| Contract engine | PASS/FAIL/INCONCLUSIVE/ERROR, empty evidence, unsupported rule | G4 |
| Replay/capture | Fresh KV contexts, matching histories, noncontiguous tensor, seeded event | G5 |
| Corpus | Stable IDs, split disjointness, tokenizer/model mismatch | G6 |
| End to end | Real self-check, candidate result, detached offline bundle | G7 |

Intended local validation commands:

~~~sh
uv sync --frozen
uv run ruff check src tests
uv run pytest tests/unit
cmake --preset host-debug
cmake --build --preset host-debug
ctest --test-dir build/host-debug --output-on-failure
uv run pytest tests/integration
uv run python scripts/check_midterm.py --ledger docs/progress.yaml --min-points 50
~~~

Model/RVV tests use explicit markers and prerequisite detection. In ordinary developer runs they may skip with a reason. In `check_midterm.py`, a skipped prerequisite-dependent check cannot earn its points.

The acceptance script validates ledger weights sum to 100, prohibits duplicate evidence credits, checks referenced artifact integrity and reports accepted/blocked points. It must not infer completion from checked Markdown boxes alone.

## 18. Implementation order, effort and cutoff decisions

The original synopsis allocates 24 weeks. Reaching this midterm slice in the remaining days is an accelerated effort with a narrow diagnostic scope. Estimates below are planning ranges, not promises or hours already spent.

| Order | Work | Estimated focused hours | Dependency |
|---:|---|---:|---|
| 1 | Discovery, locks and API/intrinsic probes | 4-6 | None |
| 2 | M0 reduction programs and RVV execution | 6-10 | Discovery |
| 3 | M1 schemas/storage | 6-8 | Discovery |
| 4 | M2 build/executor infrastructure | 6-10 | M1, probes |
| 5 | M3 binary inventory | 4-6 | M0, M1 |
| 6 | M4 real-model runner | 8-12 | API probe, M2 |
| 7 | M5 metrics/contracts/controller | 8-12 | M1, M4 |
| 8 | M6 replay/capture/seeded localisation | 10-16 | M4-M5 |
| 9 | M7 frozen pilot and runs | 4-6 engineering hours plus measured run time | M4-M5 |
| 10 | M8 documents, reports and rehearsal | 6-10 | Actual evidence |
| **Total** | | **62-96 engineering hours plus target run time** | |

Several items can be worked on by different team members after interfaces are fixed. This plan does not assume multiple autonomous agents or simultaneous changes to shared files.

### Calendar for actual implementation after authorization

- **First session:** resolve target availability, dependency locks, API probe and intrinsic probe.
- **Day 1:** reduction fixtures, schemas and artifact storage; choose and document the physical/provisional execution track.
- **Day 2:** builds, execution and binary inventory; obtain the first real-model native output.
- **Day 3:** comparator, contracts, corpus freeze and self-check; start the measured pilot.
- **Day 4:** replay, selective capture and the seeded localisation demonstration.
- **Day 5:** finish accepted evidence, report/SRS drafts, rehearsal and mentor review logistics.

If the actual start shifts, calculate remaining time from the earliest evaluation date, 6 October. Do not treat the possible 7 October slot as extra time until the team's slot is known.

### Cutoffs

- No working real-model runner by the end of Day 2: stop optional compiler matrices and focus on the runner; the planned 50% outcome is at risk.
- No reliable callback capture after one focused session: use a narrow recorded local patch at one operator, preserving diagnostic-only scope.
- Full RVV inference too slow: run the native real-model suite and RVV microbenchmarks; do not award the RVV runner points.
- No natural token divergence: retain the real PASS or numeric-only result; demonstrate FAIL/localisation with labelled injected tests.
- No verified 50-point total: report the actual total and unfinished work. Documentation or extra commits do not replace missing execution evidence.
- No selective-hardening implementation: keep O4 pending. Manual on/off diagnosis does not count as a minimum-cost policy search.

## 19. Proposed responsibilities for the four members

These assignments are suggestions for implementation and review. They do not assert past contributions or confirmed skill levels.

| Member | Proposed primary responsibility | Review responsibility |
|---|---|---|
| Anshuman Agrawal | RVV mechanism, compiler configuration, ELF/DWARF inventory and numerical controls | Runner-to-instruction claims |
| Ibteshamul Haque | C++ runner, teacher forcing, tensor capture and diagnostic hooks | Model/input isolation |
| Anshul Goel | Python orchestration, manifests, artifact store, executors and CLI | Offline reproduction |
| Aayushi Sinha | Contracts, corpus protocol, metric checks, traceability, SRS and evaluation report | Evidence completeness and exclusions |

Agree on schemas and runner protocol together before splitting modules. Require a reviewer from another workstream for each acceptance gate when the team is available. Record real authorship and reviews; commit author names must reflect actual contributions.

## 20. Commit sequence and the requested September timeline

Use small, complete changes with one-line, lowercase commit subjects of **2-5 words**, without punctuation. Keep the historical planning window separate from actual execution/test timestamps.

For this repository, explicitly set **both author and committer dates** on every new commit to the same chosen timestamp. Use daytime in **Asia/Kolkata (+05:30)**, operationally 09:00-18:00. Start the first planning commit at **2026-09-05 10:15:00 +05:30**. Every subsequent timestamp must be strictly later than both timestamps of the preceding commit, within the requested 5 September-1 October 2026 window. Reserve 1 October for final polishing. Before committing, validate the subject length and timestamp; afterwards, inspect both stored dates. Keep all commits local and **never push**.

The dates below are the **requested reconstructed development schedule**, not evidence that these changes were implemented then. If commit metadata later follows this reconstruction, document that fact in `docs/history.md`. Preserve actual build, test, corpus-freeze, meeting and experiment times. Do not rewrite existing commits, invent team attribution or create commits during this planning task.

| Logical date | Suggested one-line subject | Contents | Check before committing |
|---|---|---|---|
| 5 Sep | `add implementation plan` | Implementation plan | Weights/scope internally consistent |
| 7 Sep | `add reproducible reduction fixtures` | Complete host reducers and input generator | Host numerical tests |
| 9 Sep | `add rvv reduction probes` | Intrinsic wrappers and target probe | Compile, disassemble, execute where available |
| 11 Sep | `record stack and target manifests` | Schemas, locks and manifest validation | Schema/difference tests |
| 13 Sep | `store and verify run artifacts` | Content-addressed store and verifier | Corruption/offline tests |
| 15 Sep | `build and execute pinned stacks` | Build configuration and executors | Fresh build and timeout/error checks |
| 17 Sep | `map compiled rvv reductions` | ELF/DWARF scanner | Real ELF inventory tests |
| 19 Sep | `add the pinned model runner` | Real C++ model loading and generation | Native real-model smoke check |
| 21 Sep | `freeze inputs and capture logits` | Corpus tooling and binary logit protocol | Token/input and argmax reconstruction checks |
| 23 Sep | `compare outputs against behaviour contracts` | Alignment, metrics and rule engine | Numeric/contract tests |
| 25 Sep | `return evidence backed qualification verdicts` | Controller and four exit codes | All verdict acceptance cases |
| 27 Sep | `replay histories and capture layers` | Teacher forcing and boundary capture | Matching-history/capture checks |
| 29 Sep | `validate seeded localisation` | Diagnostic injection and on/off experiment | Seeded layer/operator location |
| 1 Oct | `polish midterm report and demo` | Static reports, SRS, traceability and demo | Full accepted-evidence checklist |

Adjust commit boundaries to real cohesive changes. Do not create empty commits to fill dates. No push, PR, message, publication or shared-service write is part of this plan; prepare any later upstream material for the user.

## 21. Mid-semester acceptance checklist

All boxes are initially unchecked.

- [ ] Dependency, model and source identities are full values rather than placeholders.
- [ ] Host reduction examples have been rerun from complete source.
- [ ] RVV probes are compiled, disassembled and executed on a named target.
- [ ] Physical Phase 0 result or its explicit blocked/negative status is recorded.
- [ ] Real-model native generation and five-run stability checks exist.
- [ ] Real-model RVV execution is verified or its points remain unearned.
- [ ] Frozen corpus, tokenizer settings and split hashes are preserved.
- [ ] Manifest differences are controlled and reported.
- [ ] All four verdicts and their exit codes are exercised.
- [ ] Real comparison results are distinct from injected test cases.
- [ ] Teacher-forced histories match and seeded localisation is confirmed.
- [ ] Missing instruction-level mapping remains visibly unresolved.
- [ ] A detached evidence bundle regenerates metrics and verdict offline.
- [ ] The completion ledger contains at least 50 accepted points under the frozen rubric.
- [ ] SRS and progress report drafts match the implementation and evidence.
- [ ] The demo works from documented commands.
- [ ] Mentor review/signatures and the required meeting-record format are handled separately using actual records.
- [ ] Remaining research work is shown in the evaluation material.

## 22. What remains after this milestone

| Objective | Mid-semester evidence | Work still needed |
|---|---|---|
| O1: qualification efficiency | Frozen pilot and margin measurements | Sensitivity selection, untouched holdout, failure recall and cost analysis |
| O2: portability envelope | Capturable reduction inputs and target metadata | Legal replay witnesses, coverage analysis and unseen implementation |
| O3: causal localisation | Shared-history replay and seeded layer/operator diagnosis | Dynamic instruction mapping, controlled reduction toggles and natural cases |
| O4: minimum-cost compatibility | Interfaces and captured failing evidence | ddmin, cost search, specialised rebuilds and clean selective/global timing |
| O5: axis separation | Manifests, instruction inventories and declared comparison axes | Complete controlled compiler/policy matrix and second implementation |
| O6: transfer | Explicit runner protocol and adapter boundary | A second runtime adapter and measured component reuse |

The next implementation action, once authorized, is the discovery/API/intrinsic probe milestone. Its output determines which target track is feasible and which acceptance gates can be demonstrated before the evaluation.
