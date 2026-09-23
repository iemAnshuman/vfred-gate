# Pilot freeze v1

Frozen on 2026-10-01 at 11:11:29.693717 UTC, before inspecting candidate differences. This is the actual timestamp; Git dates are reconstructed.

The 48 original prompts comprise eight categories of six prompts. Each category has four exploratory prompts and two held-out prompts. Group IDs separate direct and contextual prompts. The frozen manifest records exact rendered prompts, token IDs, the model and template hashes, and the source digest.

The confirmation subset is the first two exploratory IDs in each category (16 total). The smoke subset is the first ID in arithmetic, factual, formatting and code (four total). Use five independent processes per case and stack, one thread, 512-token context, and at most 32 generated tokens. Repetitions establish stability; the number of distinct cases is the statistical unit.

The self-check contract requires bit equality and exact sequences. The decision comparison requires teacher-forced greedy choices and free-running sequences to match exactly. These are development contracts. No general release guarantee or held-out predictive claim follows from this pilot.

The 16 holdout prompts remain excluded from execution. Top-two baseline logit margins are descriptive. No canary selection or threshold tuning uses the holdout. The diagnostic injection is an explicitly labelled test fixture and is not a compiler error or natural rounding discrepancy.
