# VFRED-Gate

VFRED-Gate qualifies the recorded numerical behaviour of two inference stacks against a declared contract. It archives raw logits and token histories, checks repeatability, and returns **PASS**, **FAIL**, **INCONCLUSIVE**, or **ERROR**. Teacher-forced replay can locate the earliest observed differing layer/operator. The current implementation is the host/emulator mid-semester scope in [plan.md](plan.md).

The native runner uses pinned llama.cpp and SmolLM2-360M-Instruct Q8_0. A separate freestanding RVV probe executes ordered and unordered reductions in QEMU. The native model comparison is **Apple Clang 17 versus Homebrew Clang 23 on the same ARM64 Mac**. Neither this comparison nor the injected diagnostic establishes a physical RVV defect.

## Setup

Python 3.11+, uv, CMake, Ninja and a C++17 compiler are required. LLVM tools plus `qemu-system-riscv64` are required for the RVV probe. On this Mac these prerequisites are installed. `vfg doctor` only inventories them.

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
uv run vfg doctor --output environment/host.json
uv run vfg build --stack stacks/baseline.json --build-dir build/host-release
cmake --preset host-debug
cmake --build --preset host-debug
ctest --test-dir build/host-debug --output-on-failure
uv run vfg microbench --target targets/rvv-emulator.json --output runs/mechanism-new
uv run vfg scan --binary runs/mechanism-new/probe.elf --output runs/mechanism-new/inventory.json
```

Bootstrap checks the source archive and 386 MB model against SHA-256 pins. No moving revision is resolved at runtime. Build verifies the downloaded source files against that archive, allows only the documented snapshot patch, and records compiler, effective compile-command/cache digests, source files, and executable identity. Downloaded assets, build directories and raw run bundles are intentionally ignored by Git. The original synopsis PDF remains in the repository.

The committed stack manifests record this workspace's builds. Rebuild them on another machine. For the optional compiler comparison on macOS:

```sh
uv run vfg build --stack stacks/candidate.json --build-dir build/llvm-release --compiler /opt/homebrew/opt/llvm/bin/clang++
```

Keep separate build directories for different compilers. The compiler executable's `clang++` spelling matters; resolving its symlink to `clang` changes driver behaviour. For Linux, use locally installed compiler paths and a target manifest reflecting the actual architecture. Physical-board/full-model RVV execution remains unimplemented until a compatible system is available; the freestanding QEMU target cannot execute the native model binary.

## Run the demonstration

Use a new output directory each time. Existing evidence is never silently overwritten. The corpus is already frozen; do not regenerate it under the same version.

```sh
uv run vfg validate --plan plans/smoke.json
uv run vfg qualify --plan plans/smoke.json --output runs/demo-smoke
uv run vfg qualify --plan plans/self-check.json --output runs/demo-confirmation
uv run vfg qualify --plan plans/native-comparison.json --output runs/demo-comparison
uv run vfg verify --run runs/demo-confirmation
uv run vfg report --run runs/demo-confirmation --offline --output runs/demo-confirmation/report
```

Open `runs/demo-confirmation/report/index.html` in a browser. It uses local HTML/CSS and no service. `verify` and `report` rederive metrics and the verdict from archived float32 arrays; they do not need the model, compiler, or network. To move a run, copy its entire directory. `bundle.sha256` detects accidental corruption, not malicious rewriting of both evidence and its index.

The four-case smoke run is a quick check. The confirmation contract requires 16 independent cases × two stacks × five repetitions = 160 fresh-process executions. The decision comparison adds teacher-forced execution, for 320 total. At most 32 tokens are generated per execution; context is 512, batch and microbatch are one, KV is float32, and all compute uses one CPU thread. macOS CPU affinity is unavailable and recorded as such.

| Qualification result | Exit | Meaning |
|---|---:|---|
| PASS | 0 | All rules hold on complete, stable evidence |
| FAIL | 2 | At least one rule fails on sufficient evidence |
| INCONCLUSIVE | 3 | Missing repetitions, instability, timeout, or undeclared differences |
| ERROR | 4 | Invalid inputs, corrupt outputs, or failed execution |

An expected diagnostic FAIL is a successful demonstration of the failure path. Tool invocations such as `verify` return zero when verification succeeds, even when the verified qualification verdict is FAIL. CLI usage mistakes use Typer's standard usage exit code.

## Diagnose the seeded example

`stacks/seeded.json` declares an intentionally large `+1000` perturbation to one element of `l_out-0` at the final prompt token. This tests diagnostic plumbing, not natural rounding error. After rebuilding the baseline, regenerate the seeded manifest from it with `scripts/configure_seeded.py`.

```sh
uv run python scripts/configure_seeded.py
uv run vfg qualify --plan plans/seeded.json --output runs/demo-seeded
# Expected exit 2 above; continue with the commands below.
uv run vfg localise --qualification runs/demo-seeded --case c001 --capture operator --output runs/demo-operator
uv run vfg report --run runs/demo-seeded --offline --output runs/demo-seeded/report --localisation runs/demo-operator --inventory runs/mechanism-new/inventory.json
```

Replay starts fresh contexts before, during, and after the candidate intervention. It checks identical token histories, preserves the original discrepancy, and verifies baseline restoration. The operator pass first discovers the differing layer, then saves selected operator payloads. Source/instruction attribution remains explicitly unmapped.

## Validate and inspect progress

```sh
uv run python scripts/validate.py
uv run python scripts/check_midterm.py --ledger docs/progress.yaml --min-points 50
uv run vfg progress --ledger docs/progress.yaml
```

The validation script records actual commands, timestamps, return codes, logs and JUnit results under `runs/validation`. Integration tests skip unavailable model/RVV prerequisites in ordinary developer runs; the acceptance ledger rejects skipped tests. The ledger's evidence hashes refer to the completed local demonstration. Re-running tests changes receipts; after reviewing the new results, refresh the ledger with `uv run python scripts/freeze_progress.py`.

Read [the SRS](docs/srs.md), [midterm results](docs/midterm-report.md), [walkthrough](docs/demo.md), and [requirements traceability](docs/requirements-traceability.csv). Raw binaries/model files and multi-gigabyte evidence bundles are local; a clone must reproduce or separately receive them before it can verify the recorded progress.

[Commit dates are reconstructed](docs/history.md). Actual build, dataset and experiment timestamps are preserved separately. Git history is local and no command in this project pushes or publishes it.
