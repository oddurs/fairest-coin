---
id: 75
uid: 876dd1fe-2e6b-45b3-9b18-e21e11d9e745
title: Never lose a submitted job's shots, prediction or calibration
type: bug
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p0
effort: m
area: hardware
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. Once IBM accepts a job, any failure while waiting for its result (timeout,
connection drop, Ctrl-C) leaves nothing on disk: the prediction and calibration exist only in
memory, and no command can fetch the result later. A failure in the usage call after
`job.result()` throws away shots already in hand. The fallback file written when archiving
fails omits the calibration, the circuit, the executed ops and the sampler options. And
`meta.json`'s `quantum_seconds` is null in every run because the adapter reads a key the
usage record does not have.

## Proposal

Write a pending record (prediction, calibration, circuit, plan) before submitting, and the
job id into it as soon as it exists. Collect the shots separately from the usage, so a usage
failure keeps them. Name the job id on any interruption. Add `coin recover JOB_ID` to fetch
a finished job and archive it with its pending record. Read QPU seconds from the field the
usage record actually has.

## Acceptance criteria

- [x] A failure at every step after submission (job id, result, usage, archiving, Ctrl-C) leaves a record from which `coin recover` archives the run with its original prediction and calibration (tests with a fake transport)
- [x] A usage failure after the result arrives still archives the shots
- [x] `quantum_seconds` in meta.json is filled from the usage record when it has the charge
- [x] data/README.md describes usage.json as it is written (result-time, possibly pending)

## 2026-11-02

Evidence, tests/test_hardware.py and tests/test_ibm.py. Every failure point after submission is covered with a fake transport: the job id reported (on_submitted), timeout, dropped connection, Ctrl-C while waiting, a disk that refuses the id, archiving failing (OSError and Ctrl-C), a process that dies after archiving, recovery racing recovery, a record left in the temp dir, a record with no id (maybe_submitted, --record), duplicate and unreadable records. In each, coin recover archives the run with its original prediction (written_at before submitted_at, which write_run enforces) and calibration, never twice. A usage failure keeps the shots; quantum_seconds comes from qpu_charge_time_seconds. Three review rounds: /code-review high and two adversarial passes; their findings (best-effort callback, what-ran details in the record, archived-means-done, lock-based 'still waiting', --record checks, discard guard, given runs_dir decides) each have a test. Removing the adapter's on_submitted call fails a test.

## Result

submit writes a pending record before submitting, names the job the moment IBM assigns it (with what ran and when), and keeps the result if archiving fails; coin recover [JOB_ID] [--record FILE] [--discard FILE] [--force] archives from it, never twice, never under the wrong id. Usage failures keep the shots; QPU seconds come from the usage record's charge.
