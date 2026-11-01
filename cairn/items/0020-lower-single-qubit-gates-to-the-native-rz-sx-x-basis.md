---
id: 20
uid: a33f4ea7-c957-4122-b17c-1fbbe9d216bf
title: Lower single-qubit gates to the native rz/sx/x basis
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 7
- 8
- 15
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] Property test: the lowered circuit equals the original up to global phase for random unitaries
- [x] H lowers to exactly rz(π/2), sx, rz(π/2)
- [x] The QASM 3 output parses with `qiskit.qasm3.loads` in a test (Qiskit as a test-only dependency)
- [x] Gates outside the native set are never emitted, checked by a test

## 2026-11-01

From spike 0015: native set confirmed as rz, sx, x (and cz) on all three Heron r2 backends.

## 2026-11-01

Decomposition: strip phase to SU(2), read theta=2*atan2(|b|,|a|) (atan2 stays accurate at theta near 0 and pi where arccos loses digits), phi+lam and phi-lam from the phases of a and b. Shortest form by theta: ~0 one rz; ~pi rz+x; ~pi/2 rz,sx,rz; otherwise rz,sx,rz(theta+pi),sx,rz (Qiskit's ZSX form). SNAP=1e-12 picks the shorter form only within rounding residue; each snap moves an entry by <= SNAP/2. Property tolerance LOWERED=10*SNAP: 20,000 random runs of up to 20 gates erred by <= 7e-15, inputs at the snap edge by 4.5e-13. Merging flushes a qubit's pending unitary at any two-qubit gate or measurement touching it and at the end (ascending qubit order), so cross-qubit interleaving of independent 1q gates can move; per-qubit order is preserved. Physical layout deliberately stays out of compile.py: the adapter passes initial_layout to transpile, as the 0015 spike did. to_qasm accepts rz/sx/x/cz + measure only, so cx raises until 0037 lowers it. Qiskit added to the dev group only; tests also cross-check every coin.gates matrix against qiskit.circuit.library, including two-qubit order.

## Result

coin/compile.py: lower(Circuit)->Circuit merges each run of consecutive single-qubit gates per qubit into one unitary and emits at most rz,sx,rz,sx,rz (one rz if diagonal, rz+x if antidiagonal, rz,sx,rz if theta=pi/2; identity rz dropped; rz angles in (-pi, pi]); cx/cz and measurements pass through in place. Equal up to global phase within 1e-11 (SNAP=1e-12 snapping). H -> rz(pi/2), sx, rz(pi/2). to_qasm(Circuit)->str emits OpenQASM 3 on virtual qubit[n] q / bit[n] c with repr angles, accepts only NATIVE={rz,sx,x,cz} plus measure, else ValueError naming the gate (so cx must be lowered by 0037 first). Physical layout is not in the QASM: pass it to transpile(initial_layout=..., optimization_level=0). Qiskit is a dev-only dependency; library code still never imports it.

## 2026-11-01

Independent review: 20,000 Haar-random unitaries round-trip through to_qasm, qasm3.loads and Operator within 1e-15; no correctness bug. Three weak tests let mutants survive (snap at θ≈π widened, small rz dropped, cx added to NATIVE); fixed with hand-written cases, and all three mutants are now killed by the intended tests. .hypothesis/ is now gitignored.
