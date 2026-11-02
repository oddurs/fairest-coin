---
id: 69
uid: f0e32a13-8a2b-4825-9be5-e090faac8d93
title: Find out why the chip-map prediction missed
type: spike
status: backlog
milestone: v0.3
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: noise
qpu: true
depends_on:
- 23
---

## Question

The chip-map run (data/runs/2026-11-02-dbjuh5d6p51s73cljo60) put 31 of 150 qubits within 3σ
of a prediction built from that hour's published calibration, with no per-qubit correlation
between predicted and observed bias. Is the miss in the readout calibration, in state
preparation, or in drift?

## Why it has to be answered before the work

Chapter 2 can only offer candidates. Readout mitigation (0029) assumes a trustworthy
confusion matrix, and chapter 3 needs to know whether the bias it removes is stable.

## Options

- The published readout numbers do not describe readout during a simultaneous 156-qubit
  measurement (crosstalk, or a different calibration protocol)
- Coherent gate error: an over- or under-rotated `sx` biases the coin directly, and
  randomized benchmarking's `gate_error` does not carry the sign
- Drift: the qubits changed between calibration and run, and within the run
- Two-level-system defects on a few qubits (q59 at 79.8% tails)

## What would settle it

One job, three circuits on every qubit in parallel, run back to back: prepare |0⟩ and
measure, prepare |1⟩ and measure, and the coin. The first two measure readout under the
coin's own conditions; the coin's residual after that readout is state preparation. Repeat
the coin a second time in the same job to separate drift from bias. Estimate the cost with
`coin run chip-map --dry-run`-style arithmetic and get the owner's approval first.

## Answer

<!-- Filled in when the spike closes. A spike closed without an answer was wasted. -->
