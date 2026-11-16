#!/bin/bash
# usage: sbatch scripts/rostam/job.sh NAME SUBCOMMAND [options...]   (SUBCOMMAND: compare | check)
set -u
name=$1; cmd=$2; shift 2
cd "$HOME/vfred-gate"
export VFG_CACHE=$HOME/vfg-cache
case "$(uname -m)" in
  # binutils 2.42 (system module) assembles the T-Head vector kernels; Fedora 38 ships 2.39
  riscv64) module load binutils/2.42 2>/dev/null; . .venv-riscv64/bin/activate; run() { vfg "$@"; } ;;
  aarch64) export PATH="$HOME/.local/uv-aarch64/bin:$PATH" ;&
  *) export UV_PROJECT_ENVIRONMENT=.venv-$(uname -m); uv sync -q --python 3.12; run() { uv run vfg "$@"; } ;;
esac
run "$cmd" --model "${VFG_MODEL:-models/smollm2-360m-instruct-q8_0.gguf}" --output "runs/$name" "$@" > "runs/$name.json" 2> "runs/$name.log"
echo "exit=$?" >> "runs/$name.log"
