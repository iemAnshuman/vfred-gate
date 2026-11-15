# VFRED-Gate v1: product plan (draft, 16 Nov 2026)

Status: DRAFT. Anshuman owns the logic. The decisions in section 9 go through `/socratic` and into `LOGIC.md` before code changes.

## 1. Goal

Turn VFRED-Gate from a one-machine research artifact into a tool that any llama.cpp user can run:

> "I changed my build (new commit, new flags, new backend, new CPU). Do I still get the same tokens? If not, where did the difference start, and is it a legal floating-point difference or a bug?"

Product A (general tool) is the product. Product B (the RVV reduction study) is the flagship demo inside it.

## 2. What already exists, and what is different

| Tool | What it does | What it does not do |
|---|---|---|
| llama.cpp `test-backend-ops` | Compares each ggml op on a backend with the CPU reference (NMSE). | No full-model run, no tokens, no verdict for a release. |
| llama.cpp `llama-perplexity --kl-divergence` | KL divergence and "same top p" between two runs over a text set. | No location of the difference, no contract, no CI verdict. |
| infer-check (PyPI, Apache 2.0) | Differential tests across engines, quantisations and concurrency. | Works at the output level. No op-level localisation, no legality check. |
| infer-determinism | Finds where vLLM GPU kernels stop being deterministic. | GPU/vLLM only. |

Sources: [test-backend-ops docs](https://www.mintlify.com/ggml-org/llama.cpp/development/testing), [perplexity README](https://sources.debian.org/src/llama.cpp/7965%2Bdfsg-1/tools/perplexity/README.md), [infer-check](https://pypi.org/project/infer-check/), [infer-determinism](https://github.com/JonSnow1807/infer-determinism).

"Diff two runs" is already crowded. The wedge for VFRED-Gate is the three parts that nobody else combines:

1. **Verdict:** a declared contract and a CI exit code (PASS/FAIL/INCONCLUSIVE/ERROR), re-derivable offline.
2. **Explain:** the first differing layer and ggml op, found by teacher-forced replay.
3. **Legality:** for a reduction, is the observed value inside the legal-tree envelope? "Legal difference" and "bug" are different answers.

## 3. Target user (to confirm)

First user: a developer who ports or tunes a llama.cpp CPU backend (RVV, ARM SVE, new x86 flags) and needs to know if a change alters model output. Second: a RISC-V board team that ships llama.cpp. Third: reviewers who reproduce the research result.

## 4. Definition of done for v1.0

A new user on Linux x86-64, Linux arm64 or macOS arm64 can:

```sh
pip install vfred-gate
vfg compare --model any.gguf --a llama.cpp@<ref-or-dir> --b llama.cpp@<ref-or-dir> [--flags-b "..."]
```

and receive, without hand-editing JSON:

- a verdict and exit code;
- a static HTML report with the first divergent token, layer and op;
- an envelope result for captured reductions;
- a sealed bundle that `vfg verify` re-derives offline.

Plus: CI green on three platforms, a docs site, a 2-minute demo, and one real case study.

## 5. Phases

Each phase ends with a check that I run and report. Times are estimates for agent work with Anshuman's review, not promises.

### Phase 0: logic and repo split (1 session)

- `/socratic` on section 9; record answers in `LOGIC.md`; add `.own-logic`.
- Move the academic material (100-point ledger, midterm/final reports, prereg, evidence) to `research/`. The root README becomes user-facing.
- Check: `scripts/check_midterm.py` and `verify_completion.py` still pass from the new paths.

### Phase 1: a fresh clone works (2-3 sessions)

- GitHub Actions: Linux x86-64, Linux arm64, macOS arm64. Run ruff, pytest, the native build and a smoke `qualify` with a small model.
- `vfg doctor` reports missing tools with the exact install command.
- `vfg fetch-model`: download a pinned small GGUF with hash check (default stays SmolLM2-360M Q8_0, or 135M for CI speed).
- Generated lock files: `vfg build` writes the stack JSON with hashes. No user copies a SHA by hand.
- Dockerfile with every tool, for one-command reproduction.
- Check: on a clean Linux container, `README` quickstart gives PASS in under 15 minutes.

### Phase 2: any model, any two builds (3-4 sessions)

- `vfg compare` as the main command. It builds the runner against any llama.cpp commit, tag or local checkout, with per-side CMake flags.
- Default prompt set: a frozen, licence-clean, generic corpus that the tool tokenises per model (the current corpus is tied to one tokenizer).
- Contract presets: `bit`, `numeric`, `decision`, `sequence`, selectable with one flag.
- Handle llama.cpp API drift: test the runner against a window of recent llama.cpp tags; fail with a clear message outside the window.
- Check: three models (two architectures, two quantisations) x two llama.cpp commits on CI give correct verdicts; a seeded change gives FAIL.

### Phase 3: explain and legality (3-4 sessions)

- `vfg explain`: run automatically after a FAIL. Teacher-forced replay, capture, report the first differing layer/op and the token step.
- Map the op to the ggml kernel source file (via the existing ELF/DWARF scanner where symbols exist).
- Envelope check for captured reduction operands; label each difference "inside legal envelope", "outside", or "not assessed".
- HTML report: one page, divergence timeline, op table, envelope result.
- Check: the seeded diagnostic localises to `l_out-0`/`ADD`; a real `-ffp-contract=fast` FAIL localises to an op in `ggml-cpu/ops.cpp`, which agrees with the ddmin result.

### Phase 4: RVV targets (3-5 sessions)

- Full-model run on RVV under `qemu-riscv64` user mode (cross-compiled llama.cpp with `GGML_RVV=ON`). Slow, but it closes "no full-model RVV execution".
- SSH executor for a real board: copy the runner and model, run, fetch the bundle, check hashes.
- Check: SmolLM2 runs end to end on QEMU RVV and gives a verdict against the host.

### Phase 5: the real finding (depends on hardware)

- Run `GGML_RVV=ON` vs `OFF`, and RVV vs host, on a real RVV 1.0 board. SpacemiT K3 has RVV 1.0 hardware ([Phoronix](https://www.phoronix.com/review/risc-v-rvv-vector-benchmarks)); sven0 stays the RVV 0.7.1 data point.
- Also run one non-RVV case that users care about, for example two llama.cpp releases on x86, or AVX2 vs AVX-512 builds.
- Write the case study: what differed, where, legal or not. If a real bug appears, prepare an upstream issue draft for Anshuman.
- Check: every number in the case study comes from a sealed bundle that `vfg verify` re-derives.

### Phase 6: ship (2 sessions)

- v1.0.0 on PyPI, tagged release, docs site, demo GIF, CHANGELOG, CONTRIBUTING, licence check.
- Launch drafts: blog post, llama.cpp GitHub Discussion, r/LocalLLaMA, RISC-V forums, Hacker News.
- Every push, release and post needs Anshuman's explicit permission, after the Claude review loop.

## 6. What makes it "famous"

I cannot promise fame. What I can control:

1. It must work on the first try from a fresh clone (Phase 1).
2. It must answer a question nobody else answers: "where and is it legal" (Phase 3).
3. It must launch with a real, surprising, verifiable finding (Phase 5). This is the biggest lever. A tool plus a real bug report gets attention; a tool alone usually does not.

## 7. Risks

| Risk | Effect | Response |
|---|---|---|
| No RVV 1.0 board | Flagship demo stays 0.7.1 + QEMU | Lead the launch with an x86/ARM finding; RVV as a section. Buying a board is Anshuman's decision. |
| llama.cpp API changes often | Runner breaks | Support a tested tag window; CI job against latest master, allowed to fail. |
| No real divergence found | Weak launch story | Report the bounded negative honestly; the seeded and `-ffp-contract` cases still show the explain feature. |
| Tensor names differ across llama.cpp commits | Localisation across commits fails | Localise only when graph names match; otherwise report the token step only. |
| Academic deliverables still needed | Repo split breaks grading evidence | Phase 0 keeps the research tree intact under `research/`. |

## 8. Out of scope for v1

GPU backends, vLLM/SGLang, multi-batch serving, task-quality metrics, a web dashboard.

## 9. Decisions for Anshuman (`/socratic`)

1. Who is the first user (section 3)?
2. Is there a university deadline, and must the 100-point ledger stay valid?
3. Scope: llama.cpp only for v1, or a plug-in interface for other engines?
4. Is the legality check a core feature or an advanced option?
5. Hardware: buy or borrow an RVV 1.0 board, or launch without one?
6. Name: keep "VFRED-Gate", or rename for a general audience?
7. Licence (none is set in `pyproject.toml` today).
8. Team: do the other three members take part in v1?
