---
id: 20
uid: a33f4ea7-c957-4122-b17c-1fbbe9d216bf
title: Lower single-qubit gates to the native rz/sx/x basis
type: feature
status: backlog
milestone: v0.2
depends_on:
- 7
- 8
- 15
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: compile
---

## Problem

IBM hardware only runs its native gates on physical qubits. Even the one-gate coin must be
rewritten: H becomes rz(π/2)·sx·rz(π/2) up to a global phase.

## Proposal

`coin/compile.py`: decompose any single-qubit unitary to ZXZXZ form (rz·sx·rz·sx·rz),
simplify to the shortest equivalent, merge adjacent rz, and map virtual to physical qubits
through a given layout. Then emit OpenQASM 3 for the lowered circuit.

## Acceptance criteria

- [ ] Property test: the lowered circuit equals the original up to global phase for random unitaries
- [ ] H lowers to exactly rz(π/2), sx, rz(π/2)
- [ ] The QASM 3 output parses with `qiskit.qasm3.loads` in a test (Qiskit as a test-only dependency)
- [ ] Gates outside the native set are never emitted, checked by a test
