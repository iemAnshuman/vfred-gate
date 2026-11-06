# ADR 0003: accept W0.board on RVV 0.7.1 hardware

Status: accepted 7 November 2026 by the project owner.

## Context

W0.board asks for four primary-board mechanism checks. The only RISC-V board available is
Rostam `sven0` (device tree `sophgo,mango`, T-Head vendor ID `0x5b7`), which implements RVV 0.7.1, not the
ratified RVV 1.0 that the rest of the project targets. RVV 0.7.1 has the same two
reduction policies: ordered `vfredosum.vs` and unordered `vfredsum.vs`, encoded with the
same bits as RVV 1.0 `vfredosum.vs` and `vfredusum.vs`.

## Decision

Accept W0.board (4 points) on the `sven0` evidence from job 220857:

1. ordered equals the scalar left fold on 20,000 of 20,000 arrays (encoding self-check);
2. unordered differs from ordered on 13,269 arrays, identical over five repetitions;
3. the executed reduction instructions are identified by their encodings;
4. all 300 dumped unordered results lie inside the legal-tree envelope.

Every document that cites this result names RVV 0.7.1.

## Consequences

- W3.rvv stays blocked: no full-model run on RVV hardware.
- W7.independent stays blocked: the envelope models RVV 1.0 rules, and a 0.7.1 board is
  not a second conformant RVV 1.0 implementation. The containment result is reported as
  research evidence only.
- W5.mechanism stays deferred: its rule names emulator evidence and a site toggle.
