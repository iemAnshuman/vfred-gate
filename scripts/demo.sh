#!/usr/bin/env bash
# Live demo: the gate passes a safe build, fails a fast-math build,
# and passes again after selective hardening. About 5 minutes on the recorded host.
# Needs the baseline, contractfast and selective builds (see docs/demo.md).
set -u
out="runs/live-demo-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"

step() {
  local name=$1 plan=$2
  echo
  echo "== $name: $plan"
  uv run vfg qualify --plan "$plan" --output "$out/$name" > "$out/$name.log" 2>&1
  local code=$?
  uv run vfg verify --run "$out/$name"
  uv run vfg report --run "$out/$name" --offline --output "$out/$name/report" > /dev/null
  echo "exit code $code  report: $out/$name/report/index.html"
}

step 1-baseline plans/smoke.json                # same build twice: expect PASS (0)
step 2-fast-math plans/contractfast-smoke.json  # -ffp-contract=fast: expect FAIL (2)
step 3-hardened plans/selective-smoke.json      # fast, but ops.cpp strict: expect PASS (0)
