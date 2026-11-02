---
id: 80
uid: b95939a6-b112-49a8-aeea-7e467236e9b7
title: Stop counting gate relaxation twice in the noise model
type: bug
status: backlog
milestone: v0.3.1
created: 2026-11-02
updated: 2026-11-02
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

- [ ] Depolarizing takes only the error relaxation does not explain, floored at 0, matching Aer's construction on a test case
- [ ] Archived predictions are untouched; tests that pinned the old values are updated with the reason
