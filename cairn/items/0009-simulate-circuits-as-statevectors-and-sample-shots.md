---
id: 9
uid: 74b7e183-d370-41e6-be1f-0ceac4aa7051
title: Simulate circuits as statevectors and sample shots
type: feature
status: backlog
milestone: v0.1
depends_on:
- 7
- 8
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: sim
---

## Problem

The ideal coin needs something that computes amplitudes and turns them into outcomes.
Writing it ourselves is the point: it is the reference every hardware result is judged
against.

## Proposal

`coin/sim.py`: `simulate(circuit) -> np.ndarray` applies each gate to a 2ⁿ statevector by
reshaping to an n-axis tensor and contracting (no 2ⁿ×2ⁿ matrices). `sample(circuit,
shots, rng) -> dict[str, int]` draws outcomes from the Born probabilities with a seeded
`numpy.random.Generator`. Measurement is terminal only; mid-circuit measurement is out of
scope.

## Acceptance criteria

- [ ] H|0⟩ gives probabilities [0.5, 0.5]; the Bell circuit gives {00: 0.5, 11: 0.5}
- [ ] Property test: random circuits of up to 6 qubits keep the norm at 1 to 1e-10
- [ ] Property test: tensor contraction agrees with the explicit Kronecker-product matrix for random 3-qubit circuits
- [ ] The same seed gives the same samples; a test pins this
- [ ] Adds `hypothesis` as a dev dependency for the property tests
