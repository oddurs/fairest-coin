---
id: 8
uid: b6c01ad5-bb3f-4fd3-ae4a-178e3eef82f5
title: Define the gate library as exact unitaries
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

Every prediction in the project rests on the gate matrices being right. A sign error in
`S` or a missing global phase convention silently corrupts every later chapter.

## Proposal

`coin/gates.py`: numpy matrices for I, X, Y, Z, H, S, Sdg, T, SX, RX(θ), RY(θ), RZ(θ),
CX, CZ, following Qiskit's conventions (RZ(θ) = diag(e^{-iθ/2}, e^{iθ/2})) so hardware
results line up without translation. Two-qubit matrices use the documented qubit order.

## Acceptance criteria

- [ ] Every gate is unitary to 1e-12 (property test over random angles for the rotations)
- [ ] Identities hold: H² = I, S² = Z, SX² = X, HZH = X, and CX = (I⊗H)·CZ·(I⊗H)
- [ ] The qubit-ordering convention is stated in the module docstring and tested on CX
- [ ] Adds `numpy` as the project's first runtime dependency
