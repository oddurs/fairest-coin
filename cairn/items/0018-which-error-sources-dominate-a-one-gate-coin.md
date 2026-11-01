---
id: 18
uid: 1096ef10-f133-4e95-8f8b-6c923b0e0769
title: Which error sources dominate a one-gate coin?
type: spike
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 15
- 17
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p1
effort: s
area: noise
---

## Question

For H followed by measurement on a typical IBM qubit, how much of the bias comes from
readout asymmetry, from T1 decay during the measurement window, and from gate error?

## Why it has to be answered before the work

It decides what the calibration-to-noise-model mapping must include, and it is the
prediction chapter 2 makes before any hardware is touched.

## Options

- Readout asymmetry alone (simplest model)
- Readout plus thermal relaxation over the gate and measurement durations
- Everything, including the reported gate error as depolarizing

## What would settle it

Sweep each source over the ranges published in real calibration data with the density
simulator, and tabulate its contribution to P(1) − 0.5.

## Answer

Measured with `analysis/dominant_errors.py` against the ibm_marrakesh calibration archived
with run `2026-11-01-dbjsk29ffo6c73baaosg`: each source switched on alone, per qubit, for
the 151 of 156 qubits with complete, physical calibration.

| Source | Median effect on P(tails) − 0.5 | Worst qubit |
|---|---|---|
| Readout asymmetry | **−0.44%** | 26.2% |
| T1/T2 during the 36 ns `sx` | −0.011% | 0.33% |
| Gate error as depolarizing | exactly 0 | 0 |
| Preparation error | exactly 0 | 0 |
| T1 over the 2.7 µs measurement window | −0.81% | 19.5% |

**Readout asymmetry dominates**, about 40× the next real contribution. Gate error and
preparation error cannot bias this coin at all, by symmetry: depolarizing noise keeps a
50/50 state at 50/50, and a qubit wrongly prepared in |1⟩ becomes H|1⟩ = |−⟩, also 50/50.

**The measurement-window term double counts.** IBM measures `prob_meas0_prep1` by
preparing |1⟩ and measuring it, so decay during readout is already inside the readout
calibration. Added separately it alone predicts more bias than the whole calibrated
asymmetry. It is left out of the model, and the chip map should test that choice by
recording both predictions.

**Decision for 0021:** per-qubit readout confusion from `prob_meas1_prep0` and
`prob_meas0_prep1`, plus thermal relaxation over each gate's length. Depolarizing gate
error is kept because it matters for circuits other than the coin, but it does not move
the coin's prediction.

**Data quality, which 0021 must report rather than default:** qubits 82, 94 and 130 lack
T1 and/or T2; qubits 20 and 83 report T2 > 2·T1; qubits 23, 26, 113, 119, 121 and 135 lack
`init_error`.

## Result

Readout asymmetry dominates the one-gate coin's bias (median −0.44%, worst 26%); decay during sx is ~40× smaller (−0.011%); gate and preparation error have exactly zero effect by symmetry. Measurement-window decay is already inside IBM's readout calibration, so the model excludes it. Model for 0021: readout confusion + thermal relaxation per gate (+ depolarizing for other circuits). analysis/dominant_errors.py reproduces the table from the archived run.
