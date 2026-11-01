---
id: 8
uid: b6c01ad5-bb3f-4fd3-ae4a-178e3eef82f5
title: Define the gate library as exact unitaries
type: feature
status: done
milestone: v0.1
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: s
area: sim
---

## Problem

Every prediction in the project rests on the gate matrices being right. A sign error in
`S` or a missing global phase convention silently corrupts every later chapter.

## Proposal

`coin/gates.py`: numpy matrices for I, X, Y, Z, H, S, Sdg, T, SX, RX(θ), RY(θ), RZ(θ),
CX, CZ, following Qiskit's conventions (RZ(θ) = diag(e^{-iθ/2}, e^{iθ/2})) so hardware
results line up without translation. Two-qubit matrices use the documented qubit order.

## Acceptance criteria

- [x] Every gate is unitary to 1e-12 (property test over random angles for the rotations)
- [x] Identities hold: H² = I, S² = Z, SX² = X, HZH = X, and CX = (I⊗H)·CZ·(I⊗H)
- [x] The qubit-ordering convention is stated in the module docstring and tested on CX
- [x] Adds `numpy` as the project's first runtime dependency

## 2026-11-01

Independent review planted 7 wrong matrices (Y sign, RY sign, S/Sdg swap, wrong T phase, wrong name→matrix mappings) that all passed the first test suite. Added reference matrices written independently of coin.gates and exp(-iθσ/2) checks; a replay of 8 mutants is now caught 8/8. hypothesis arrived here rather than in 0009 because the rotation criteria need property tests.

## Result

coin/gates.py: matrix(Gate) returns read-only complex128 unitaries in Qiskit conventions: RX/RY/RZ = exp(-iθσ/2), SX = e^{iπ/4}RX(π/2). Little-endian: for Gate(name, (a, b)) the matrix acts on |b a⟩, built as kron(op_b, op_a); CX control = qubits[0]. Module constants I X Y Z H S SDG T SX CX CZ and rx/ry/rz(θ) are public. numpy is the runtime dependency; hypothesis is a dev dependency.
