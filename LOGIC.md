# VFRED-Gate v1: logic decisions

On 16 Nov 2026 Anshuman delegated these decisions to Claude: "for logic. please decide yourself. just remember we have to make this a 'famous' project." Each decision below is Claude's, made under that delegation. Anshuman can overrule any of them.

## D1. Product

VFRED-Gate v1 is a numerical-compatibility gate for llama.cpp builds. One command compares two builds of llama.cpp on one GGUF model and answers three questions:

1. Do the two builds give the same output under a declared contract? (PASS / FAIL / INCONCLUSIVE / ERROR, with an exit code for CI.)
2. If not, where does the difference start (token step, layer, ggml op)?
3. Is the difference a legal floating-point reduction difference, or not assessed?

Why: "diff two runs" already exists (llama.cpp `--kl-divergence`, infer-check). A verdict, a location and a legality label together do not.

## D2. First user

A developer who changes a llama.cpp CPU build: a new commit, new compiler flags, a new SIMD backend (RVV, SVE, AVX-512). The RVV reduction study is the flagship demo.

## D3. Scope of v1

- llama.cpp only, CPU only, one sequence, one thread, greedy decoding.
- Any GGUF model the user has on disk.
- A build side is one of: `pinned` (the locked llama.cpp commit), `llama.cpp@<commit-or-tag>`, or a path to a local llama.cpp git checkout. Each side can add CMake options and compiler flags.
- GPU backends, servers and other engines are out of scope.

## D4. The research record stays frozen

The 100-point ledger, reports, prereg and evidence stay where they are, with the same bytes. The product code adds new files and keeps the old commands working. Only the root README changes; its old text moves to `docs/research/README.md` and the ledger path follows it (same SHA-256).

## D5. No hand-written hashes for users

`vfg compare` writes every lock, stack, corpus, contract and plan file itself, inside the run directory. Builds go to a cache (`~/.cache/vfred-gate`, or `$VFG_CACHE`). The tracked `stacks/*.json` files stay as research records.

## D6. Trust model for sources

- `pinned`: the archive hash in `third_party/llama.lock.json` must match.
- `llama.cpp@<ref>`: the tag or commit resolves to a 40-hex commit; the archive hash is recorded on first download and checked on every later use (trust on first use).
- Local path: must be a git checkout; the record holds the HEAD commit and a hash of `git diff HEAD`, so uncommitted changes are visible in the evidence.

## D7. Default prompts and contract

- Default prompts: the 48 prompts of `corpora/source/pilot.jsonl`, written by the team. `--cases N` takes the first N (default 16). Users can pass their own text or JSONL file.
- Default contract: `decision` (same greedy token at every teacher-forced step and same full sequence). Presets: `bit`, `decision`, `sequence`.
- Default repetitions: 3. Fewer than 2 cannot detect nondeterminism.

## D8. Explain

After a FAIL, `vfg compare` runs operator-level localisation on the first failing case. If the two builds have different graph shapes or tensor names, the report says "not aligned" and gives only the token step. It never guesses.

## D9. Legality label

The label has three values: `inside_envelope`, `outside_envelope`, `not_assessed`. v1 assigns `not_assessed` unless reduction operands were captured. The label never claims an ISA defect.

## D10. Name and licence

- Keep the name VFRED-Gate and the CLI `vfg`. The tagline carries the meaning.
- Licence: MIT, the same as llama.cpp. Confirmed by Anshuman on 16 Nov 2026: "let it be mit."

## D11. Launch rule

No push, release or post without Anshuman's explicit permission for that action, after the Claude review loop.

Status: owned (delegated to Claude, 16 Nov 2026)
