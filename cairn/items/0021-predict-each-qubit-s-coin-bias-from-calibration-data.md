---
id: 21
uid: b34a337b-7fcc-48b1-be3a-f7b2c760c8a7
title: Predict each qubit's coin bias from calibration data
type: feature
status: backlog
milestone: v0.2
depends_on:
- 17
- 18
- 19
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: noise
---

## Problem

Chapter 2's claim is "predict, then measure". That needs a mapping from IBM's published
numbers to a noise model for each qubit, and a predicted P(1).

## Proposal

`coin/noise.py`: `model_from_calibration(calibration) -> dict[int, QubitNoise]`, using
T1, T2, readout P(1|0) and P(0|1), sx error, and gate and measurement durations, with the
source list decided by the dominant-error spike. `predict_bias(model, circuit)` runs the
density simulator for each qubit.

## Acceptance criteria

- [ ] Runs from a saved calibration fixture, with no network
- [ ] A qubit with zero errors predicts exactly 0.5
- [ ] Qubits missing a calibration field are reported, not silently given defaults
- [ ] `coin predict --calibration FILE` prints a per-qubit table sorted by predicted bias

## 2026-11-01

From spike 0018: model = readout confusion (prob_meas1_prep0, prob_meas0_prep1) + thermal relaxation over each gate's length (+ depolarizing gate error for generality; zero effect on the coin). Do NOT add T1 over the measurement window: the readout calibration already contains it. In the 2026-11-01 snapshot, qubits 82/94/130 lack T1 or T2, 20/83 have T2 > 2·T1, and six lack init_error; report them, never default.
