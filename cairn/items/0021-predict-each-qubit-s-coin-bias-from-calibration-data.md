---
id: 21
uid: b34a337b-7fcc-48b1-be3a-f7b2c760c8a7
title: Predict each qubit's coin bias from calibration data
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 17
- 18
- 19
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] Runs from a saved calibration fixture, with no network
- [x] A qubit with zero errors predicts exactly 0.5
- [x] Qubits missing a calibration field are reported, not silently given defaults
- [x] `coin predict --calibration FILE` prints a per-qubit table sorted by predicted bias

## 2026-11-01

From spike 0018: model = readout confusion (prob_meas1_prep0, prob_meas0_prep1) + thermal relaxation over each gate's length (+ depolarizing gate error for generality; zero effect on the coin). Do NOT add T1 over the measurement window: the readout calibration already contains it. In the 2026-11-01 snapshot, qubits 82/94/130 lack T1 or T2, 20/83 have T2 > 2·T1, and six lack init_error; report them, never default.

## 2026-11-01

Independent review found two bugs, both fixed with tests that failed first: (1) qubits IBM marks as broken (113: sx gate_error = 1, IBM's failed-calibration placeholder; 119: reads a prepared 1 as 0 54% of the time) were published as the chip's two most biased coins; (2) malformed calibration content crashed coin predict with a traceback. Validation is now per qubit: any problem excludes that qubit with its reason; only sx and x calibrations are read, so an odd unit on an unused gate cannot break the backend; readout_length is optional (only --measurement-decay needs it). Depolarizing p = 2r is now pinned by an sx·sx test; the two depolarizing mutants that survived review are killed.

## Result

coin.noise: model_from_calibration(snapshot) → CalibrationModel(qubits: {q: QubitNoise}, excluded: {q: reason}); per-qubit validation excludes missing/nonsensical fields, unknown units, gate_error ≥ 0.5 (IBM's failed marker is 1), readout error ≥ 0.5, T2 > 2·T1, duplicate or missing sx calibration. predict_tails(noise, native_one_qubit_circuit, measurement_decay=False) = readout confusion over (thermal relaxation per gate length + depolarizing p = 2·gate_error); rz is free; unknown gates raise. CLI: coin predict --calibration RUN_DIR|FILE[.gz] [--measurement-decay] prints P(tails) sorted ascending, then exclusions. On the 2026-11-01 snapshot: 149 usable, 7 excluded (20, 82, 83, 94, 113, 119, 130).
