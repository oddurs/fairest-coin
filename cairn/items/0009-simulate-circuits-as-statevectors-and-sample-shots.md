---
id: 9
uid: 74b7e183-d370-41e6-be1f-0ceac4aa7051
title: Simulate circuits as statevectors and sample shots
type: feature
status: done
milestone: v0.1
assignee: Oddur Sigurdsson
depends_on:
- 7
- 8
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] H|0⟩ gives probabilities [0.5, 0.5]; the Bell circuit gives {00: 0.5, 11: 0.5}
- [x] Property test: random circuits of up to 6 qubits keep the norm at 1 to 1e-10
- [x] Property test: tensor contraction agrees with the explicit Kronecker-product matrix for random 3-qubit circuits
- [x] The same seed gives the same samples; a test pins this
- [x] Adds `hypothesis` as a dev dependency for the property tests

## 2026-11-01

Independent review planted 9 mutations: every axis/order/outcome-string mutation was killed (a consistently big-endian simulator only by the bit-indexing reference). Two measurement-mapping mutations (first write wins; one clbit per qubit) survived and now have pinned tests; both are killed. Probabilities below 1e-12 are dropped from probabilities() so rx(π) has no phantom '0'. The reference matrix is built by bit indexing rather than pure Kronecker products, because Kronecker products alone cannot express a two-qubit gate on non-adjacent qubits.

## Result

coin/sim.py: simulate(circuit) → 2ⁿ statevector from |0…0⟩ (little-endian, tensordot per gate, terminal measurement only, gates after measuring a qubit raise ValueError); probabilities(circuit) → exact {outcome: p}, dropping p ≤ NEGLIGIBLE=1e-12; sample(circuit, shots, rng) → counts via one multinomial draw from a required numpy Generator. Outcome strings: classical bit 0 rightmost, unmeasured clbits read 0, later measurement into a clbit overwrites (as on hardware).
