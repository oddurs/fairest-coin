---
id: 26
uid: eb56e354-871e-4f6b-a5ad-507684a5b7bc
title: 'Write chapter 2: predict the real coin'
type: docs
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 25
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: m
area: essay
---

## Problem

This is where the project turns from simulation into science: write a prediction, then
measure it.

## Proposal

`docs/chapters/02-predict-the-real-coin.md`: why noise needs density matrices, what T1 and
readout error are, the dominant-error result, the prediction made in advance, the chip map,
and an honest account of where the model missed.

## Acceptance criteria

- [x] Every number quoted is traceable to a named archived run
- [x] Discusses at least one qubit the model got wrong, and why it might have
- [x] Linked from the README's chapter index

## 2026-11-01

Independent review checked the physics and recomputed the numbers. It caught: an overstated drift claim (a few qubits, not the chip; now a count of 8 of 156 against 0.4 expected), the coherent bound compared after readout without scaling by contrast (132 became 131), a 'four times' that held only against the chip median, and loose wording. _drift also returned z in reversed bit order, caught by a test; it now maps by physical qubit. All numbers in the chapter come from coin compare (run by the chapter tests), the pycon examples, or recomputation from the two archived runs.

## Result

docs/chapters/02-predict-the-real-coin.md: the calibration-based prediction failed (31 of 150 within 3σ, zero correlation, median sign reversed). Candidates quantified: coherent sx error permitted by the published gate_error (131 of 150 within 3σ once allowed), stale readout calibration (q118), and drift in 8 qubits. Adds coin compare RUN and noise.coherent_bias_bound.
