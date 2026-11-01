---
id: 15
uid: acbb53d1-1bf4-43f2-87ed-59eedd619246
title: How do we reach IBM hardware, and what does a job cost?
type: spike
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

Answered by job `dbjsk29ffo6c73baaosg`, archived in
`data/runs/2026-11-01-dbjsk29ffo6c73baaosg/`.

**What the Open Plan gives.** 10 minutes of QPU time per 28-day cycle on one instance
(us-east), and three 156-qubit Heron r2 processors: `ibm_fez`, `ibm_kingston`,
`ibm_marrakesh`. Queues differ a lot: 68, 14 and 0 pending jobs at the time of the run.

**Native gates.** `rz`, `sx`, `x` and `cz` (plus measure, reset, delay and `if_else`) on all
three. Single-qubit lowering targets rz/sx/x; the two-qubit entangler is CZ.

**Authentication.** `QiskitRuntimeService(channel="ibm_quantum_platform", token=…,
instance=…)` with both `QISKIT_IBM_TOKEN` and `QISKIT_IBM_INSTANCE` (the instance CRN).
Reading backends, calibration and job records costs no QPU time.

**Calibration.** `backend.properties().to_dict()` gives per-qubit T1, T2, readout error,
`prob_meas1_prep0`, `prob_meas0_prep1`, gate errors and durations: 1.4 MB of JSON per
snapshot, 60 KB gzipped. The snapshot used was last updated 37 minutes before the run.

**Submission.** Our own OpenQASM 3, parsed by `qiskit.qasm3.loads` (needs the
`qiskit-qasm3-import` package), then `transpile(..., initial_layout=[q],
optimization_level=0)`, which passed the hand-lowered `rz, sx, rz, measure` through
unchanged. `SamplerV2` worked but is deprecated since qiskit-ibm-runtime 0.50.0 in favour
of the client-side `executor_sampler.Sampler`; the adapter (0022) should use the new one.

**Cost.** One qubit, 4,096 shots: **3 QPU seconds** charged (8 s wall clock from
submission to result, about 5 s of it running). The usage record reads `pending` when the
result arrives and settles to `complete` shortly after, so the archive must fetch it again.
An all-qubit job was not run, since only this one was approved; 0023 measures it.

**The result.** Qubit 139, chosen for the best readout on the chip (P(1|0) = 0.0010,
P(0|1) = 0.0020), was predicted at 2,046 ± 32 tails of 4,096 and gave **2,071**: 0.8σ
from the prediction, and 0.7σ from a perfectly fair coin. Choosing the best of 156 qubits
makes its calibration optimistic; this sample cannot tell.

**What it means for the plan.** Across the chip, readout error predicts a median bias of
−0.44% (towards heads, as decay to |0⟩ suggests), with outliers from −26% to +14%. One
4,096-shot job resolves ±0.78% (1σ), so a single chip-wide job at that depth resolves only
the 9 qubits predicted beyond 3σ. Seeing the typical qubit's bias needs roughly 10⁵ shots
per qubit. At about 3 s per small job the cycle allows roughly 200 such jobs.

## Result

Open Plan: 10 QPU-min per 28-day cycle; ibm_fez, ibm_kingston, ibm_marrakesh (156-qubit Heron r2). Native: rz, sx, x, cz. Auth: channel ibm_quantum_platform + QISKIT_IBM_TOKEN + QISKIT_IBM_INSTANCE. Calibration via backend.properties() (1.4 MB, gzip 60 KB). Submit own QASM 3 via qasm3.loads + transpile(initial_layout, optimization_level=0) + Sampler (SamplerV2 deprecated; use executor Sampler). 1-qubit 4,096-shot job = 3 QPU s. First coin: 2,071/4,096 tails vs predicted 2,046±32. Typical qubit bias (−0.44%) needs ~10⁵ shots to resolve.
