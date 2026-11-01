---
id: 15
uid: acbb53d1-1bf4-43f2-87ed-59eedd619246
title: How do we reach IBM hardware, and what does a job cost?
type: spike
status: backlog
milestone: v0.2
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: hardware
qpu: 'true'
---

## Question

What does the Open Plan give us today (backends, monthly QPU allowance), how do we fetch a
backend's calibration data, how do we submit an OpenQASM 3 circuit through the Sampler,
and how many QPU seconds do a 4,096-shot one-qubit job and an all-qubit job actually use?

## Why it has to be answered before the work

The adapter, the run archive's calibration format, single-qubit lowering (which needs the
native gate set) and the hardware budget for v0.2–v0.4 all depend on these answers.

## Options

- Submit our own QASM 3 through `qiskit-ibm-runtime`'s SamplerV2 (parse with
  `qiskit.qasm3.loads`), and let Qiskit do nothing else
- Call the Qiskit Runtime REST API directly with no Qiskit dependency at all

## What would settle it

One real job submitted and its usage read back from the job metadata, the calibration
JSON saved to disk, and the native gate set and coupling map written down.

## Answer

<!-- Filled in when the spike closes. -->
