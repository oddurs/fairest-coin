---
id: 7
uid: 13d690c2-2c82-4658-b5aa-ead97abad1dc
title: Describe circuits with a tiny immutable IR
type: feature
status: backlog
milestone: v0.1
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: sim
---

## Problem

The simulator, the noise model, the compiler and the QASM emitter all need to talk about
the same circuit. Without one shared description each grows its own, and they drift.

## Proposal

`coin/circuit.py`: a frozen dataclass `Circuit(n_qubits, ops)` where each op is a frozen
`Gate(name, qubits, params)` or `Measure(qubit, clbit)`. Builder methods return new
circuits (`c.h(0).measure(0, 0)`). No execution logic lives here.

## Acceptance criteria

- [ ] `Circuit(1).h(0).measure(0, 0)` builds the coin; the original circuit is unchanged
- [ ] Referencing a qubit outside `range(n_qubits)` raises `ValueError` naming the qubit
- [ ] A gate given the wrong number of qubits or parameters raises `ValueError`
- [ ] Circuits compare equal by value and are hashable
