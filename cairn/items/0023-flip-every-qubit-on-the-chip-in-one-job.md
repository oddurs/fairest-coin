---
id: 23
uid: af678808-0b5a-491f-b7c6-09b97f985bd5
title: Flip every qubit on the chip in one job
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 21
- 22
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: s
area: hardware
qpu: 'true'
---

## Problem

The chip has over a hundred qubits, which makes it over a hundred different coins. One job
measures all of them and turns "the real coin is biased" into a map.

## Proposal

`coin run chip-map --backend NAME`: predict every qubit's bias from that day's calibration,
write `prediction.json`, then submit H + measure on all qubits at once and archive.

## Acceptance criteria

- [x] `--dry-run` prints the circuit, the predictions and the estimated QPU cost without submitting
- [x] At least one real run is archived under `data/runs/`
- [x] The run's predictions predate its submission, as shown by the timestamps in `meta.json`

## 2026-11-01

From spike 0015: one 4,096-shot job resolves ±0.78% per qubit, but the median predicted bias is −0.44%, so only ~9 of 156 qubits would stand out. Plan ~10⁵ shots per qubit, check the per-job shot limit and cost before submitting, and get approval for the budget. All-qubit job cost is still unmeasured.

## 2026-11-01

From spike 0018: record two predictions per qubit, readout-only (the model) and readout + measurement-window decay (the double-counting alternative). The chip map then tests which one the hardware agrees with.

## 2026-11-01

From 0022: the executor Sampler has dry_run=True to estimate usage without QPU execution, but the adapter uses SamplerV2 (proven on hardware) for now. Estimate the chip-map cost from the backend's rep delay, readout and gate lengths times shots, and from spike 0015's 3 s per 4,096-shot job.

## 2026-11-01

Tooling built: coin run chip-map --backend NAME --shots N (--dry-run | --submit). Live dry run on ibm_marrakesh, 2026-11-01: 156 qubits, 100,000 shots (1σ ≈ 0.16%), 150 predicted (median bias −0.45%, range −4.18% to +14.25%), 83 resolvable beyond 3σ, 6 excluded with reasons, ~27 QPU seconds estimated. Criteria 2 and 3 wait for the owner-approved real run, which the owner submits.

## 2026-11-01

Real run archived: data/runs/2026-11-02-dbjuh5d6p51s73cljo60 (ibm_marrakesh, 156 qubits, 100,000 shots, job dbjuh5d6p51s73cljo60). Prediction written 01:34:10.286Z, submitted 01:34:12.543Z. Billed 29 QPU s against the 27 s estimate. Calibration last updated 11 minutes before submission. The prediction failed: 31 of 150 qubits within 3σ for the readout-only model, 16 for the measurement-decay alternative. Observed median bias +0.45% against a predicted −0.45%; per-qubit correlation r = −0.002. Reversed bit order and inverted bits were checked and do not rescue it (best r = 0.13). Qubits readout cannot explain: q59 tails 79.8% with readout errors 10%/7%; q118 fair at 50.03% though its calibration reads 47% of |0⟩ as 1. Bias drifts within the 25 s job (half-vs-half z spread 2.2, 1.0 expected). The readout-only model is still closer than the alternative on 129 of 150 qubits.

## Result

Archived as data/runs/2026-11-02-dbjuh5d6p51s73cljo60 (ibm_marrakesh, 156 qubits × 100,000 shots, 29 QPU s, per-shot memory kept). The calibration-based prediction failed: 31 of 150 qubits within 3σ, zero per-qubit correlation between predicted and observed bias, and the chip-wide median came out +0.45% against a predicted −0.45%. Bias also drifts within the job. Spike 0069 asks why.
