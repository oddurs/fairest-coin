---
id: 66
uid: 4e749089-507d-49f2-9848-3aa6b0f57b0c
title: Move the IBM adapter to the client-side executor Sampler
type: chore
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
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
- [x] The archived options show twirling and dynamical decoupling disabled after the switch
- [x] No deprecation warning remains in the adapter

## 2026-11-05

Dry run, 2026-11-05, run by the owner (analysis/executor_dry_run.py, ibm_marrakesh, qubit 104): refused before any job existed, 'Unable to use dry_run mode: backend mock_marrakesh was not found'; dry_run needs a mock backend this account does not have. No job, no QPU time. Before failing it showed the finalized options: twirling enable_gates=False, enable_measure=False; dynamical decoupling enable=False. The result shape was then seen locally instead: the executor Sampler on FakeMarrakesh in local mode (needs qiskit-aer) returns qiskit PrimitiveResult → SamplerPubResult with .data: DataBin, .data.c: BitArray, .metadata; get_bitstrings() gives 100 strings; the job has metrics(). This is the same post-processing a real job gets: the result's semantic_role (sampler_v2) is stored with the result server-side, and decoders/executor/decoder.py dispatches on it, so a job fetched by id (coin recover) decodes the same way. The adapter's reading code, result[0].data.c.get_bitstrings(), is unchanged by the switch.

## 2026-11-05

Switched: sampler_for builds qiskit_ibm_runtime.executor_sampler.Sampler with the same options; result reading unchanged. qiskit-aer joins the dev group only, so the adapter's local-run tests execute the executor Sampler offline through its real client-side post-processing. All 26 adapter tests pass with every warning filter removed and warnings as errors: no deprecation warning remains. A local run's archived options show twirling (gates, measure) and dynamical decoupling disabled. Criterion 1 is left unticked: IBM refused the dry run, so the shape recorded before the change is the local-mode one, with the reason it carries over. The first real executor job (0039's hardware run) will show it on hardware.

## Result

The IBM adapter uses the executor Sampler, with twirling and dynamical decoupling off and no deprecation warning; results read unchanged. IBM refused the dry run (no mock backend for this account), so the result shape was confirmed in local mode on FakeMarrakesh instead; the first hardware run (0039) confirms it on a real job.

## 2026-11-05

Confirmed on hardware 2026-11-05 by 0039's run (job dbme92m74qds73ds595g): the executor Sampler's result read through result[0].data.c.get_bitstrings() unchanged, 10,000 shots archived, usage charged 5 s, and the archived options show twirling (gates and measure) and dynamical decoupling disabled.
