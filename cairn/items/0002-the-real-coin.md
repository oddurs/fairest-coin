---
id: 2
uid: 9e3550ff-f8e7-4bdf-ae17-84d3576d45c4
key: v0.2
title: The real coin
type: milestone
status: backlog
created: 2026-11-01
updated: 2026-11-01
priority: p2
due: 2026-11-22
---

## Ships

`coin predict` forecasts every qubit's coin bias from IBM's calibration data, and the
whole-chip experiment measures it: one job, 100+ coins, predicted against measured.
Chapter 2 tells the story.

## Done when

- [ ] A density-matrix simulator with noise channels reproduces the statevector on pure states
- [ ] Per-qubit bias predictions are written to the run archive *before* the job is submitted
- [ ] The whole-chip run is archived under `data/runs/` with its calibration snapshot
- [ ] The chip-map and predicted-vs-measured figures regenerate from the archive alone
- [ ] Chapter 2 states how good the prediction was, including where it failed
- [ ] Tagged `v0.2.0`

## Explicitly not in this milestone

- Fixing the bias: v0.2 only explains it
- Two-qubit circuits on hardware
