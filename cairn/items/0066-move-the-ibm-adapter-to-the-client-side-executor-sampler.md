---
id: 66
uid: 4e749089-507d-49f2-9848-3aa6b0f57b0c
title: Move the IBM adapter to the client-side executor Sampler
type: chore
status: backlog
milestone: v0.4
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: hardware
---

## Problem

`coin/ibm.py` uses SamplerV2, the path spike 0015 proved on hardware. SamplerV2 is deprecated
since qiskit-ibm-runtime 0.50.0, to be removed no sooner than three months after that release,
in favour of `qiskit_ibm_runtime.executor_sampler.Sampler`, whose results come back through
an Executor with client-side post-processing. Its result shape has not been seen on a real
job, so switching blind risks a run whose QPU time is spent but whose result cannot be read.

## Proposal

Use the executor Sampler's `dry_run=True` (server-side validation with schema-preserving mock
data, no QPU execution) to confirm the result shape and that twirling and dynamical
decoupling stay off, then switch `sampler_for` and the result extraction.

## Acceptance criteria

- [ ] A dry run's result shape is recorded in this item before any code changes
- [ ] The archived options show twirling and dynamical decoupling disabled after the switch
- [ ] No deprecation warning remains in the adapter
