---
id: 22
uid: ea86066c-9cff-4d11-9679-b730b9fdb2fc
title: Submit circuits to IBM through one isolated adapter
type: feature
status: backlog
milestone: v0.2
depends_on:
- 15
- 19
- 20
created: 2026-11-01
updated: 2026-11-01
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

- [ ] `import coin` works without the `ibm` extra installed; a test checks this
- [ ] A missing token exits non-zero with a message saying which variable to set
- [ ] Submission is tested against a fake transport with no network
- [ ] A finished job's QPU seconds are recorded in `meta.json`
- [ ] The token never appears in logs, archives or error messages, checked by a test

## 2026-11-01

From spike 0015: channel='ibm_quantum_platform' needs QISKIT_IBM_INSTANCE (the CRN) as well as QISKIT_IBM_TOKEN. SamplerV2 is deprecated since qiskit-ibm-runtime 0.50.0; use executor_sampler.Sampler. qasm3.loads needs the qiskit-qasm3-import package.
