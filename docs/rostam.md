# Rostam capability check

On 1 October 2026, Slurm partition `risc5` exposed nodes `sven0` and `sven1`. The probe ran on `sven0.rostam.cct.lsu.edu`: Linux riscv64 6.1.55, 64 CPUs, device-tree compatible string `sophgo,mango`.

Each job requested one CPU, 256 or 512 MB, CPU binding and a two-minute wall limit, with a ten-second queue cutoff. Executables had a five-second timeout and core dumps disabled. Probe files used private `mktemp` directories on the compute node. No full model was uploaded or executed.

GCC 13.2.1 lacked `riscv_vector.h`. Clang 16.0.6 compiled the RVV 1.0 probe, which caught SIGILL and reported `unsupported_instruction`. The staged retry failed during vector configuration at `vsetivli a1,4,e32,m1,ta,mu`.

This target could not execute the compiled standard-RVV probe. The failure alone does not identify its vector revision. Physical-target validation and full-model RVV execution remain blocked; the QEMU results are recorded separately.

Jobs 201666 and 201667 completed in one second each, with peak step memory of 52,284 KB and 46 MB. Job 201665 stopped at compilation in under one second. The final queue check found no active VFRED-Gate jobs. Probe directories were retained for inspection.

Raw logs are under `runs/rostam/`; small receipts are tracked under `evidence/midterm/runs/rostam/`.

## Follow-up on 7 November 2026: RVV 0.7.1 probe

The node reports `mvendorid 0x5b7` (T-Head). Its vector unit implements the
pre-ratification RVV 0.7.1 (XTheadVector), which has no `vsetivli`; that explains the
October SIGILL. Neither Clang 16 on the node, binutils 2.42 nor Homebrew Clang 23 accepts
`-march=rv64gc_xtheadvector`, so `microbench/rvv/thead/reduce.S` hand-encodes the vector
instructions and `probe.c` checks the encoding against the scalar left fold.

Job 220857 ran on `sven0` with 1 CPU, 256 MB and a two-minute limit, in a private
`mktemp` directory, with core dumps disabled. Results, five identical repetitions:

- ordered equals scalar on 20,000 of 20,000 arrays;
- unordered differs from ordered on 13,269 of 20,000 arrays;
- all 300 dumped small-array results lie inside the legal-tree envelope (VLMAX 4).

Raw log and manifest: `evidence/completion/rostam-thead/`.
