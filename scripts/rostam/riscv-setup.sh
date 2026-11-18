#!/bin/bash
# One-time setup on Rostam sven0 (riscv64): a Rust toolchain to build pydantic-core, then vfred-gate.
set -eu
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}"
if [ ! -x "$HOME/.cargo/bin/cargo" ]; then
  curl -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh
  sh /tmp/rustup-init.sh -y --profile minimal --no-modify-path
fi
export PATH="$HOME/.cargo/bin:$PATH" CARGO_BUILD_JOBS=32
[ -d .venv-riscv64 ] || python3.11 -m venv --system-site-packages .venv-riscv64
. .venv-riscv64/bin/activate
pip install -q --upgrade pip
pip install -q pydantic typer ninja || pip install -q pydantic typer
pip install -q --no-deps -e .
python -c "import vfg.cli, pydantic; print('ok', pydantic.__version__)"
vfg doctor | python -c "import json,sys; d=json.load(sys.stdin); print(d['architecture'], d['compare_ready'], d['compare_missing'])"
