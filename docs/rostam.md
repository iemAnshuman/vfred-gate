# Rostam capability check

On 1 October 2026, the user authorized careful use of `ssh rostam`. Discovery used the existing SSH alias and Slurm, not direct unscheduled computation on the login node. The `risc5` partition exposed idle `sven0` and `sven1` nodes. The selected node was `sven0.rostam.cct.lsu.edu`, Linux riscv64 6.1.55, 64 CPUs, with device-tree compatible string `sophgo,mango`.

Every probe requested one CPU, 256 or 512 MB, a two-minute wall limit, immediate allocation with a ten-second queue cutoff, and CPU binding. Executable probes additionally used a five-second timeout and disabled core dumps. Source and binaries were written only to `mktemp` private directories on the compute node. No packages, configuration, user jobs or system services were changed. No model was uploaded and no full inference workload was submitted.

The installed GCC 13.2.1 lacked `riscv_vector.h`, so its attempt stopped at compilation. Installed Clang 16.0.6 compiled the RVV 1.0 intrinsic probe. Execution raised SIGILL, which the probe caught and reported as `unsupported_instruction`. The staged retry failed at stage 1 (vector configuration); disassembly shows
`vsetivli a1,4,e32,m1,ta,mu` there. The retry and disassembly are archived under `runs/rostam`. This establishes that this compiled standard-RVV probe does not execute on that target; the advertised `v` ISA letter alone does not establish compatibility with the toolchain's vector revision.

The exact hardware vector revision is not inferred from the failure. Supporting a legacy vector target would require an explicit target/toolchain adapter and separate validation. Consequently the physical-board mechanism and full-model RVV credits remain unearned. The local QEMU RVV 1.0 experiment remains a separate emulator result.

Small private probe directories are recorded in the logs and left for inspection. There are no background VFRED-Gate jobs after the blocking `srun` commands returned.

Scheduler accounting reports jobs 201666 and 201667 completed in one second each,
with step peak memory of 52,284 KB and 46 MB respectively. Job 201665 failed at
compilation in under one second. A final name-filtered queue check found no active
VFRED-Gate jobs. The raw accounting output is retained with the probe logs.
