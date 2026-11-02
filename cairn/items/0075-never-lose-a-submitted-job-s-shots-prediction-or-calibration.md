---
id: 75
uid: 876dd1fe-2e6b-45b3-9b18-e21e11d9e745
title: Never lose a submitted job's shots, prediction or calibration
type: bug
status: backlog
milestone: v0.3.1
created: 2026-11-02
updated: 2026-11-02
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

- [ ] A failure at every step after submission (job id, result, usage, archiving, Ctrl-C) leaves a record from which `coin recover` archives the run with its original prediction and calibration (tests with a fake transport)
- [ ] A usage failure after the result arrives still archives the shots
- [ ] `quantum_seconds` in meta.json is filled from the usage record when it has the charge
- [ ] data/README.md describes usage.json as it is written (result-time, possibly pending)
