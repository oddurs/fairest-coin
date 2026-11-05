---
id: 46
uid: f4d98e09-17a8-4efe-ae64-26b4d77f73ba
title: 'Write chapter 4: two coins that agree'
type: docs
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 39
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
priority: p0
effort: m
area: essay
---

## Problem

The reader meets entanglement through the coin, and sees a circuit compiled for real
hardware.

## Proposal

`docs/chapters/04-two-coins-that-agree.md`: Bell pairs, why agreement alone proves
nothing (two coins glued together also agree), native-gate compilation and pair selection.

## Acceptance criteria

- [x] Shows the lowered circuit that actually ran
- [x] Explains why agreement alone is not evidence of anything quantum
- [x] Linked from the README's chapter index

## 2026-11-05

docs/chapters/04-two-coins-that-agree.md: the Bell pair simulated; glued coins (a copied random sequence) agree just as well, so agreement read in one basis is no evidence of anything quantum; the lowered circuit that actually ran, printed from the archive, with the hardware's own gate counts (one cz, three sx); pair choice by the two-qubit noise model (coin predict --pairs on the run's calibration); the run (coin compare) and its lopsided miss traced to qubit 6's readout of |1⟩ (196 against 37), which is why later runs use measured readout; and the bridge to chapter 5, agreement at every angle as cos²(θ/2). Every example and command is run by tests/test_chapters.py. README links it and names coin run bell and coin predict --pairs.

## Result

Chapter 4 written and linked: the Bell pair, why agreement alone proves nothing (glued coins agree too), the lowered circuit that ran, pair selection, and the 97.67% agreement on ibm_marrakesh 5-6 with its readout-driven miss.
