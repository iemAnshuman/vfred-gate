# VFRED-Gate

VFRED-Gate compares the numerical behaviour of two inference stacks. It archives logits and token histories, checks repeatability, and returns **PASS**, **FAIL**, **INCONCLUSIVE**, or **ERROR**. Replay helps locate the earliest differing layer or operator.

The midterm implementation uses pinned llama.cpp and SmolLM2-360M-Instruct Q8_0. Native comparisons run on ARM64; RVV reduction probes run separately in QEMU. Full-model execution on physical RVV hardware remains pending.

## Quick start

Install Python 3.11+, uv, CMake, Ninja, and a C++17 compiler. RVV probes additionally need LLVM tools and QEMU.

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
uv run vfg build --stack stacks/baseline.json
uv run vfg qualify --plan plans/smoke.json --output runs/demo
uv run vfg report --run runs/demo --offline --output runs/demo/report
```

Open `runs/demo/report/index.html`. Use a new output directory for each run. Bootstrap downloads and verifies the pinned source and model. Models, builds, and raw evidence are excluded from Git; rebuild locally to reproduce results.

See the [walkthrough](docs/demo.md) for comparisons, diagnostics, and validation; the [SRS](docs/srs.md), [midterm report](docs/midterm-report.md), and [plan](plan.md) cover scope and progress.

[Commit dates are reconstructed](docs/history.md); actual experiment timestamps are preserved in evidence.
