---
id: 16
uid: e837e1cb-16a8-4165-ad7f-66018d4176d6
title: Extend the simulator to density matrices
type: feature
status: backlog
milestone: v0.2
depends_on:
- 9
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: sim
---

## Problem

Noise turns pure states into mixtures, and a statevector cannot represent a mixture. This
upgrade is itself the lesson of chapter 2.

## Proposal

`coin/sim.py` gains `simulate_density(circuit, noise=None) -> np.ndarray`, evolving ρ as a
2n-axis tensor: unitaries as UρU†, channels as Σ KρK†. Measurement probabilities come from
the diagonal.

## Acceptance criteria

- [ ] For noiseless circuits ρ equals |ψ⟩⟨ψ| from the statevector to 1e-10 (property test)
- [ ] ρ stays Hermitian, positive semidefinite and trace 1 under random circuits and channels
- [ ] Runs a 5-qubit circuit in under one second
