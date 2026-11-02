---
id: 29
uid: 7773f79e-a34b-4db3-93c8-dc4c5414c868
title: Mitigate readout error on estimated distributions
type: feature
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 17
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p2
effort: s
area: extract
---

## Problem

Readout error skews every estimate of the bias. Mitigation corrects estimates, but it
cannot make an individual bit fair, and the code and chapter must keep that distinction.

## Proposal

`coin/extract.py`: estimate the confusion matrix from calibration circuits (prepare |0⟩,
prepare |1⟩) and correct observed distributions by constrained inversion, keeping the
result a valid probability distribution.

## Acceptance criteria

- [x] Simulated round trip: apply a known confusion matrix, mitigate, recover the original within sampling error
- [x] Never returns negative probabilities
- [x] The docstring says plainly that mitigation acts on distributions, not on bits

## 2026-11-01

From 0023: the published readout calibration did not predict the chip-map coin (r = −0.002 per qubit; q118's calibration says 47% of |0⟩ reads as 1, yet its coin was fair). Estimate the confusion matrix from our own calibration circuits, as proposed, and never from the backend's properties. Spike 0069 runs those circuits.

## 2026-11-01

Evidence, tests/test_mitigate.py. (1) Exact round trip for 1-4 bits under random readouts (property test), and a sampled 100,000-shot coin recovered within 4σ where the raw frequency is >10σ off. (2) Property test with 20-shot samples and true zeros: never negative, sums to 1; a test shows raw inversion alone goes negative. Removing the simplex projection fails 2 tests. (3) A test pins the docstring's 'acts on distributions, not on bits'. Module is coin/mitigate.py, not extract.py: mitigation corrects estimates, it does not extract bits. Review fixes: multi-bit calibration counts (bit=), refuses counts/NaN/out-of-range, a named MIN_CONTRAST (0.05) instead of a determinant test, refuses >20 bits (dense).

## Result

coin.mitigate: readout_from_counts(prepared_0, prepared_1, bit=) and mitigate(measured, errors), inversion of per-bit confusion matrices then Euclidean projection onto the simplex. Refuses readouts with contrast < 0.05 and widths > 20 bits.
