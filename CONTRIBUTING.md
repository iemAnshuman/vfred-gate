# Contributing

## Set up

```sh
uv sync
uv run vfg doctor
uv run ruff check .
uv run pytest -q
```

Tests that need the demo model or native tools skip when those are missing. To run them, fetch the model into `models/` with `uv run python scripts/bootstrap.py`.

## Rules

- A command never prints an illustrative result. If it cannot produce evidence, it returns `INCONCLUSIVE` (exit 3) or `ERROR` (exit 4).
- Do not change files under `docs/research/`, `evidence/` or the files listed in `docs/progress.yaml`; the ledger hashes them.
- Keep commit subjects to one short line.

## Report a numerical difference

Attach `summary.json` and the `report/` folder of the run. They contain the build identities, the contract and the first differing operator.
