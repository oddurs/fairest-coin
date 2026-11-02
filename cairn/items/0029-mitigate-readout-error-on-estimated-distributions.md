---
id: 29
uid: 7773f79e-a34b-4db3-93c8-dc4c5414c868
title: Mitigate readout error on estimated distributions
type: feature
status: backlog
milestone: v0.3
depends_on:
- 17
created: 2026-11-01
updated: 2026-11-01
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

- [ ] Simulated round trip: apply a known confusion matrix, mitigate, recover the original within sampling error
- [ ] Never returns negative probabilities
- [ ] The docstring says plainly that mitigation acts on distributions, not on bits

## 2026-11-01

From 0023: the published readout calibration did not predict the chip-map coin (r = −0.002 per qubit; q118's calibration says 47% of |0⟩ reads as 1, yet its coin was fair). Estimate the confusion matrix from our own calibration circuits, as proposed, and never from the backend's properties. Spike 0069 runs those circuits.
