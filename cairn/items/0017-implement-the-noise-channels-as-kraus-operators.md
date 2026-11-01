---
id: 17
uid: ceb465c0-fd4f-40f5-b77e-a15cc1c4412d
title: Implement the noise channels as Kraus operators
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 16
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] Every channel satisfies Σ K†K = I to 1e-12
- [x] Amplitude damping takes |1⟩ to P(1) = e^{-t/T1}, checked against the closed form
- [x] Thermal relaxation rejects T2 > 2·T1 with `ValueError`, since that is unphysical
- [x] Readout with P(1|0)=0.02, P(0|1)=0.05 on a perfect 50/50 coin gives P(1) = 0.485 exactly

## 2026-11-01

Tests compare against closed forms (e^{-t/T1} populations, 0.5·e^{-t/T2} coherence, depolarized ρ, the 0.485 readout example). Four planted physics errors were each caught: dephasing missing its factor 2, dephasing ignoring amplitude damping's share of T2, swapped readout asymmetry, wrong depolarizing weight.

## Result

coin.noise: amplitude_damping(γ, q), phase_damping(λ, q), thermal_relaxation(T1, T2, t, q) → (amplitude damping, phase damping) with 1/Tφ = 1/T2 − 1/(2T1), rejecting T2 > 2T1; depolarizing(p, q) in Qiskit's ρ→(1−p)ρ+p·I/2 convention. Readout(p1_given_0, p0_given_1) and apply_readout(probabilities, {clbit: Readout}) act on outcome distributions, never on ρ. Times share the caller's unit.
