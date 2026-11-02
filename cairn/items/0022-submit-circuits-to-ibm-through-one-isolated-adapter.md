---
id: 22
uid: ea86066c-9cff-4d11-9679-b730b9fdb2fc
title: Submit circuits to IBM through one isolated adapter
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 15
- 19
- 20
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: m
area: hardware
---

## Problem

Real runs need authentication, submission, polling and result parsing, and none of that
should leak into the library: Qiskit is transport, not a foundation.

## Proposal

`coin/ibm.py` is the only module that imports Qiskit, via an optional `ibm` dependency
group. It reads the API key from the `QISKIT_IBM_TOKEN` environment variable, fetches
calibration, submits lowered QASM 3 via SamplerV2, waits, and writes the complete run
through the archive.

## Acceptance criteria

- [x] `import coin` works without the `ibm` extra installed; a test checks this
- [x] A missing token exits non-zero with a message saying which variable to set
- [x] Submission is tested against a fake transport with no network
- [x] A finished job's QPU seconds are recorded in `meta.json`
- [x] The token never appears in logs, archives or error messages, checked by a test

## 2026-11-01

From spike 0015: channel='ibm_quantum_platform' needs QISKIT_IBM_INSTANCE (the CRN) as well as QISKIT_IBM_TOKEN. SamplerV2 is deprecated since qiskit-ibm-runtime 0.50.0; use executor_sampler.Sampler. qasm3.loads needs the qiskit-qasm3-import package.

## Result

coin.hardware (no Qiskit): Submission(circuit native, backend, layout, shots, calibration, prediction) validates at construction; submit(transport, submission, runs_dir, submit_script=None) refuses before submission unless the prediction is timezone-aware and written earlier, then archives the whole run via write_run. Transport protocol: calibration(backend) -> dict, run(backend, qasm, layout, shots) -> JobResult. coin.ibm (the only Qiskit import, extra 'ibm'): IBMTransport reads QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE (MissingCredentialsError names the variable), scrubs credentials from every IBMError, maps our QASM onto the layout with optimization_level=0 and refuses if mapping changes any gate, runs SamplerV2 with twirling and DD explicitly off, and archives the options and executed ops.

## 2026-11-01

Independent review found two bugs, both fixed with tests that failed first: (1) routing slipped past the mapping check, because swaps are built from native gates and only gate names were compared; the check now compares every instruction, its angles and its physical qubits, in order. (2) A failure after the job ran lost the shots and the job id; submit now checks archivability (JSON, writable runs_dir) before submitting, saves a .unarchived-<job>.json and names the job if archiving fails, and every transport error after submission names the job. Errors are raised outside the except block so the unscrubbed original is neither cause nor context. A full run now executes offline against a local GenericBackendV2.
