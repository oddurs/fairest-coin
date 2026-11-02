---
id: 2
uid: 9e3550ff-f8e7-4bdf-ae17-84d3576d45c4
key: v0.2
title: The real coin
type: milestone
status: done
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p2
due: 2026-11-22
---

## Ships

`coin predict` forecasts every qubit's coin bias from IBM's calibration data, and the
whole-chip experiment measures it: one job, 100+ coins, predicted against measured.
Chapter 2 tells the story.

## Done when

- [x] A density-matrix simulator with noise channels reproduces the statevector on pure states
- [x] Per-qubit bias predictions are written to the run archive *before* the job is submitted
- [x] The whole-chip run is archived under `data/runs/` with its calibration snapshot
- [x] The chip-map and predicted-vs-measured figures regenerate from the archive alone
- [x] Chapter 2 states how good the prediction was, including where it failed
- [x] Tagged `v0.2.0`

## Explicitly not in this milestone

- Fixing the bias: v0.2 only explains it
- Two-qubit circuits on hardware

## 2026-11-01

Evidence: tests/test_density.py::test_noiseless_density_is_the_pure_state (property test); data/runs/2026-11-02-dbjuh5d6p51s73cljo60 with prediction written 2.3 s before submission and calibration.json.gz; docs/figures/chip-map.svg and prediction-scatter.svg checked by scripts/figures --check in CI; docs/chapters/02-predict-the-real-coin.md; tag v0.2.0.

## Result

Shipped as v0.2.0. The calibration-based prediction of every qubit's coin bias failed on ibm_marrakesh: 31 of 150 qubits within 3σ, zero correlation, median sign reversed. Chapter 2 attributes it to coherent sx error the published gate_error cannot reveal, readout calibrations that did not describe the job's readout, and drift in a few qubits. Spike 0069 (v0.3) is set up to separate them.
