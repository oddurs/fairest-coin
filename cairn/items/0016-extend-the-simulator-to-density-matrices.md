---
id: 16
uid: e837e1cb-16a8-4165-ad7f-66018d4176d6
title: Extend the simulator to density matrices
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 9
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] For noiseless circuits ρ equals |ψ⟩⟨ψ| from the statevector to 1e-10 (property test)
- [x] ρ stays Hermitian, positive semidefinite and trace 1 under random circuits and channels
- [x] Runs a 5-qubit circuit in under one second

## 2026-11-01

Independent review: all 15 planted mutations in the core maths (conjugation side, axis formulas, qubit reversal, Kraus handling) were killed except three, now covered: Measure channels skipped, channel qubit order reversed, shape check removed. It also found two bugs, fixed with tests that failed first: a channel qubit outside the circuit silently wrapped to another qubit, and noise could act on an already-measured qubit.

## Result

coin.sim: Channel(kraus, qubits) validates shape, completeness (Σ K†K = I to 1e-10) and distinct qubits. Noise = Callable[[Gate | Measure], Iterable[Channel]]: channels apply after a Gate, and before readout for a Measure; channels outside the circuit or on already-measured qubits raise. simulate_density(circuit, noise=None) → 2ⁿ×2ⁿ ρ; probabilities(..., noise=None) and sample(..., noise=None) use the density path when noise is given. Shared hypothesis strategies live in tests/strategies.py (tests is now a package).
