# Rostam capability check

On 1 October 2026, Slurm partition `risc5` exposed nodes `sven0` and `sven1`. The probe ran on `sven0.rostam.cct.lsu.edu`: Linux riscv64 6.1.55, 64 CPUs, device-tree compatible string `sophgo,mango`.

Each job requested one CPU, 256 or 512 MB, CPU binding and a two-minute wall limit, with a ten-second queue cutoff. Executables had a five-second timeout and core dumps disabled. Probe files used private `mktemp` directories on the compute node. No full model was uploaded or executed.

GCC 13.2.1 lacked `riscv_vector.h`. Clang 16.0.6 compiled the RVV 1.0 probe, which caught SIGILL and reported `unsupported_instruction`. The staged retry failed during vector configuration at `vsetivli a1,4,e32,m1,ta,mu`.

This target could not execute the compiled standard-RVV probe. The failure alone does not identify its vector revision. Physical-target validation and full-model RVV execution remain blocked; the QEMU results are recorded separately.

Jobs 201666 and 201667 completed in one second each, with peak step memory of 52,284 KB and 46 MB. Job 201665 stopped at compilation in under one second. The final queue check found no active VFRED-Gate jobs. Probe directories were retained for inspection.

Raw logs are under `runs/rostam/`; small receipts are tracked under `evidence/midterm/runs/rostam/`.
