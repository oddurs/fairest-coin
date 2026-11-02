---
id: 69
uid: f0e32a13-8a2b-4825-9be5-e090faac8d93
title: Find out why the chip-map prediction missed
type: spike
status: doing
milestone: v0.3
assignee: Oddur Sigurdsson
claimed: 2026-11-02
depends_on:
- 23
created: 2026-11-01
updated: 2026-11-02
priority: p1
effort: s
area: noise
qpu: true
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

## 2026-11-01

A later calibration (owner's dry run, 2026-11-02 ~02:53 UTC, not archived) newly flags qubits 34, 48 and 59 as readout-broken: p(1|0) = 0.56, 0.65 and 0.75. In the chip-map run they came up tails 65.2%, 64.9% and 79.8%, among the worst misses. So for these three the miss was most likely readout that went bad before the calibration caught it, not state preparation. The spike's prepare-|0⟩ circuit tests exactly this; archive a fresh calibration with it.

## 2026-11-01

From spike 0028: coupled qubits 113 and 119, both excluded by the calibration model, are anticorrelated at −123σ (r ≈ −0.39) in the same shot. No other coupled pair shows crosstalk. Worth one line in the spike's readout circuits.

## 2026-11-02

Tooling built: coin run readout --backend --shots N --prepare {0,1} (--dry-run|--submit), predicted from each qubit's published readout straight from the snapshot (so qubits the model excludes, including the broken-readout ones, are tested too); readout.measured(run0, run1) gives per-qubit Readout as the jobs saw it. Deviation from the plan: three back-to-back jobs (prepare 0, prepare 1, a fresh chip map), not one job, because the adapter and the archive hold one circuit per job; drift between jobs is a caveat, drift within each job is still measurable. Proposed budget: 20,000 shots per readout job (~7 s each) and 100,000 for the chip map (~27 s).
