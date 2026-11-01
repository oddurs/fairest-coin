---
id: 17
uid: ceb465c0-fd4f-40f5-b77e-a15cc1c4412d
title: Implement the noise channels as Kraus operators
type: feature
status: backlog
milestone: v0.2
depends_on:
- 16
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: noise
---

## Problem

Real qubits relax (T1), dephase (T2), suffer imperfect gates and misread. Each needs to be
a channel the density-matrix simulator can apply.

## Proposal

`coin/noise.py`: amplitude damping(γ), phase damping(λ), thermal relaxation(T1, T2, t)
built from those two, depolarizing(p), and an asymmetric readout confusion matrix with
P(1|0) ≠ P(0|1). Readout is a classical map on outcome probabilities, not a Kraus channel,
and the code keeps the two apart.

## Acceptance criteria

- [ ] Every channel satisfies Σ K†K = I to 1e-12
- [ ] Amplitude damping takes |1⟩ to P(1) = e^{-t/T1}, checked against the closed form
- [ ] Thermal relaxation rejects T2 > 2·T1 with `ValueError`, since that is unphysical
- [ ] Readout with P(1|0)=0.02, P(0|1)=0.05 on a perfect 50/50 coin gives P(1) = 0.485 exactly
