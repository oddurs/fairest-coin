---
id: 80
uid: b95939a6-b112-49a8-aeea-7e467236e9b7
title: Stop counting gate relaxation twice in the noise model
type: bug
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p3
effort: s
area: noise
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. `predict_tails` applies T1/T2 over the gate and then depolarizing at p = 2·gate_error,
but the reported gate error already includes relaxation. Qiskit Aer subtracts the relaxation
part first (and uses no depolarizing where relaxation alone exceeds the error). The effect on
this coin is about 7e-8, but deeper circuits in v0.4 would be mispredicted.

## Acceptance criteria

- [x] Depolarizing takes only the error relaxation does not explain, floored at 0, matching Aer's construction on a test case
- [x] Archived predictions are untouched; tests that pinned the old values are updated with the reason

## 2026-11-02

Depolarizing now takes only the error relaxation does not explain: p = 2(r − r₁)/(1 − 2r₁), 0 where relaxation alone exceeds r, as Qiskit Aer builds device noise. Property test: relaxation plus that depolarizing has average infidelity exactly r (the old p = 2r construction fails it). No existing test pinned the old values. Recomputing the first chip map's predictions changes P(tails) by at most 1.3e-5, against 1σ = 1.6e-3 at 100,000 shots; archived predictions are untouched.

## Result

noise.average_infidelity and noise.gate_depolarizing; predict_tails no longer counts gate relaxation twice. Effect on the coin ≤ 1.3e-5.
