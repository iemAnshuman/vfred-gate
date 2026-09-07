# ADR 0001: native host and emulated RVV development

Status: accepted for the midterm software milestone, 1 October 2026.

The available development machine is an ARM64 macOS host. Physical RVV hardware
has not been identified. Use native CPU inference and QEMU RVV microbenchmarks
while preserving target identity in every result.

The original physical Phase 0 gate remains blocked. Emulated vector execution
does not earn physical-hardware points. No cross-board portability or hardware
performance claim follows from this track. Full RVV model execution is a
separate subitem and must be measured before it receives credit.

