---
id: 23
uid: af678808-0b5a-491f-b7c6-09b97f985bd5
title: Flip every qubit on the chip in one job
type: feature
status: backlog
milestone: v0.2
depends_on:
- 21
- 22
created: 2026-11-01
updated: 2026-11-01
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

- [ ] `--dry-run` prints the circuit, the predictions and the estimated QPU cost without submitting
- [ ] At least one real run is archived under `data/runs/`
- [ ] The run's predictions predate its submission, as shown by the timestamps in `meta.json`

## 2026-11-01

From spike 0015: one 4,096-shot job resolves ±0.78% per qubit, but the median predicted bias is −0.44%, so only ~9 of 156 qubits would stand out. Plan ~10⁵ shots per qubit, check the per-job shot limit and cost before submitting, and get approval for the budget. All-qubit job cost is still unmeasured.

## 2026-11-01

From spike 0018: record two predictions per qubit, readout-only (the model) and readout + measurement-window decay (the double-counting alternative). The chip map then tests which one the hardware agrees with.

## 2026-11-01

From 0022: the executor Sampler has dry_run=True to estimate usage without QPU execution, but the adapter uses SamplerV2 (proven on hardware) for now. Estimate the chip-map cost from the backend's rep delay, readout and gate lengths times shots, and from spike 0015's 3 s per 4,096-shot job.
