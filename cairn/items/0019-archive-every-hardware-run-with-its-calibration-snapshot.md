---
id: 19
uid: 29bc6d76-6e85-469f-9df2-4b2786e7aeed
title: Archive every hardware run with its calibration snapshot
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 7
- 15
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] Writing a run that has no prediction fails unless the caller explicitly opts out
- [x] Round-trip test: write a run, load it, get back an equal `Run`
- [x] Loading a run with a missing or malformed file raises an error naming the file
- [x] The format is documented in `data/README.md`

## 2026-11-01

From spike 0015: the first run fixed the layout (circuit.qasm, prediction.json, calibration.json.gz, counts.json, memory.txt with per-shot bits, meta.json, submit.py, usage.json). Timestamps must be sub-second: prediction and submission shared a second. Gzip the calibration (1.4 MB → 60 KB). Usage reads 'pending' at result time, so fetch the final record afterwards into its own file rather than editing meta.json.

## 2026-11-01

Run is one frozen dataclass and write_run takes a Run, so the round trip is literally load_run(write_run(dir, run)) == run. The opt-out from a prediction is allow_no_prediction=True plus a no_prediction_reason string recorded in meta.json, because the loader must later tell a deliberate omission from a lost file. The first run's prediction written_at equals its submitted_at at second resolution; the loader accepts it as written (immutable data) and the test proves order against IBM's microsecond 'created' timestamp instead. Its meta.json 'qubit' loads as qubits=(139,); new runs write 'qubits'. Unmodelled meta keys (IBM timestamps, transpiled_ops, result-time usage) survive in Run.extra. qpu_seconds prefers usage.json over meta quantum_seconds, which was null. memory.txt keeps the first run's concatenated one-line format; width comes from counts keys, and the loader checks the shots tally to counts. Calibration is gzipped with mtime=0 so identical snapshots give identical bytes. All validation runs before the directory is created, so a refusal leaves nothing behind.

## Result

coin/archive.py (stdlib only): frozen Run(job_id, backend, qubits: tuple[int,...], shots, submitted_at, finished_at: aware datetimes, circuit_qasm, counts: dict[str,int], calibration: dict, prediction: Prediction|None, no_prediction_reason, prediction_dryrun, memory: tuple[str,...]|None, quantum_seconds, usage: dict|None, library_version, submit_script, extra: dict of unmodelled meta.json keys); Prediction(written_at, values). load_run(path) -> Run raises ArchiveError naming the file for a missing required file, malformed JSON/gzip or inconsistent counts/memory. write_run(runs_dir, run, *, allow_no_prediction=False) -> Path writes runs_dir/<UTC submission date>-<job id>/ and refuses: no prediction (unless opted out with a no_prediction_reason), prediction.written_at not strictly before submitted_at, naive timestamps, counts not summing to shots, memory not tallying to counts, an existing directory. Run.qpu_seconds prefers usage.json's qpu_charge_time_seconds. Format, documented in data/README.md: required meta.json, circuit.qasm, counts.json, calibration.json.gz, prediction.json; optional memory.txt (per-shot outcomes concatenated on one line), prediction-dryrun.json, submit.py, usage.json; new timestamps ISO-8601 UTC with microseconds; data/runs is immutable.
