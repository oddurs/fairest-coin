---
id: 19
uid: 29bc6d76-6e85-469f-9df2-4b2786e7aeed
title: Archive every hardware run with its calibration snapshot
type: feature
status: backlog
milestone: v0.2
depends_on:
- 7
- 15
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: hardware
---

## Problem

Calibrations drift daily, so a hardware run can never be repeated. The archive *is* the
experiment, and QPU seconds are too scarce to lose a result.

## Proposal

`coin/archive.py` and `data/runs/<UTC date>-<job id>/`: `circuit.qasm`, `prediction.json`
(written before submission), `calibration.json`, `counts.json`, `meta.json` (backend,
qubits, shots, QPU seconds, library version). A loader returns a typed `Run`. Archives
are committed to git.

## Acceptance criteria

- [ ] Writing a run that has no prediction fails unless the caller explicitly opts out
- [ ] Round-trip test: write a run, load it, get back an equal `Run`
- [ ] Loading a run with a missing or malformed file raises an error naming the file
- [ ] The format is documented in `data/README.md`

## 2026-11-01

From spike 0015: the first run fixed the layout (circuit.qasm, prediction.json, calibration.json.gz, counts.json, memory.txt with per-shot bits, meta.json, submit.py, usage.json). Timestamps must be sub-second: prediction and submission shared a second. Gzip the calibration (1.4 MB → 60 KB). Usage reads 'pending' at result time, so fetch the final record afterwards into its own file rather than editing meta.json.
