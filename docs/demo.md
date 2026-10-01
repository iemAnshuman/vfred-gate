# Mid-semester walkthrough

## Setup and smoke run

Install Python 3.11+, uv, CMake, Ninja, and a C++17 compiler. RVV probes additionally need LLVM tools and QEMU.

```sh
uv sync --frozen
uv run python scripts/bootstrap.py
uv run vfg build --stack stacks/baseline.json
uv run vfg qualify --plan plans/smoke.json --output runs/demo
uv run vfg report --run runs/demo --offline --output runs/demo/report
```

Open `runs/demo/report/index.html`. Use a new output directory for each run. Bootstrap downloads and verifies the pinned source and model. Models, builds, and raw evidence are excluded from Git; rebuild locally to reproduce results.

## Recorded results

1. Open `docs/midterm-report.md` and explain the host/emulator results and pending hardware work.
2. Show the source/model locks, frozen corpus split and `plans/self-check.json`. Show that the holdout IDs do not appear in the selected cases.
3. Run `uv run vfg verify --run runs/self-check`. Open its report and point to 16 distinct cases, 160 complete executions, the bit-equality rule and the stability count.
4. Open the native compiler-comparison report. Explain the two actual compilers, declared manifest differences and separate free-run/teacher-forced rules. A PASS applies only to the recorded pilot.
5. Show `runs/mechanism/inventory.json` and `stdout.json`: ordered/unordered RVV instructions and their QEMU results. Both policies matched on the tested cases.
6. Open the seeded report. Show the +1000 test injection, FAIL, first token difference, shared history, earliest `l_out-0` / `ADD`, and baseline restoration.
7. Run `uv run python scripts/check_midterm.py --min-points 50`. Show accepted and blocked points, the tests behind each credit, and the next milestones.
8. If a live run is requested, use `plans/smoke.json` and a new output directory. Do not overwrite archived evidence. Use the recorded smoke cost to explain expected runtime; do not start a broad remote experiment during the demonstration.

## Submission

Keep the SRS at `docs/srs.md` locally; it is excluded from Git. The progress ledger checks this local copy along with the archived run bundles. Bring signed hard copies of the report and SRS, plus the prescribed meeting record.

Evaluation is on 6 and 7 October 2026. Reporting time is 9:45 AM; evaluation runs from 10:00 AM to 1:00 PM.
