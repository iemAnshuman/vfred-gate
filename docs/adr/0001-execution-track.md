# ADR 0001: native host and emulated RVV development

Status: accepted for the midterm software milestone, 1 October 2026.

The available development machine is an ARM64 macOS host. Rostam RISC-V hardware was discovered and probed on 1 October; the compiled
RVV 1.0 capability probe raised a caught SIGILL. See `docs/rostam.md`. A compatible
primary target has not been established. Use native CPU inference and QEMU RVV microbenchmarks
while preserving target identity in every result.

The original physical Phase 0 gate remains blocked. Emulated vector execution
does not earn physical-hardware points. No cross-board portability or hardware
performance claim follows from this track. Full RVV model execution is a
separate subitem and must be measured before it receives credit.

