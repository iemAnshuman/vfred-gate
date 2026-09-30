# Mid-semester walkthrough

1. Open `docs/midterm-report.md` and explain the exact host/emulator scope and the unearned hardware/research points. The synopsis is a proposal, not completed experimental evidence.
2. Show the source/model locks, frozen corpus split and `plans/self-check.json`. Show that the holdout IDs do not appear in the selected cases.
3. Run `uv run vfg verify --run runs/self-check`. Open its report and point to 16 distinct cases, 160 complete executions, the bit-equality rule and the stability count.
4. Open the native compiler-comparison report. Explain the two actual compilers, declared manifest differences and separate free-run/teacher-forced rules. A PASS applies only to the recorded pilot.
5. Show `runs/mechanism/inventory.json` and `stdout.json`. There are actual ordered/unordered RVV instructions and QEMU executions. Explain that matching outputs on these cases do not disprove non-associativity or establish a board result.
6. Open the seeded report. Show the declared +1000 injection, FAIL, first token difference, shared history, earliest `l_out-0` / `ADD`, and baseline restoration. Explicitly call this an injected diagnostic check.
7. Run `uv run python scripts/check_midterm.py --min-points 50`. Show accepted and blocked points, the tests behind each credit, and the next milestones.
8. If a live run is requested, use `plans/smoke.json` and a new output directory. Do not overwrite archived evidence. Use the recorded smoke cost to explain expected runtime; do not start a broad remote experiment during the demonstration.

For the university evaluation, bring hard copies of the project report and SRS with real mentor signatures. Maintain actual meeting records in the prescribed format when supplied. No meetings or signatures have been invented. Evaluation dates: 6 and 7 October 2026; report at 9:45 AM; evaluation 10:00 AM–1:00 PM, as stated in the supplied notice.
