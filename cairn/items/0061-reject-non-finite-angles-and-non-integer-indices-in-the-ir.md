---
id: 61
uid: 9fe2ffa6-eb18-48f3-9bb6-0a15c94e2f1b
title: Reject non-finite angles and non-integer indices in the IR
type: bug
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p1
effort: s
area: sim
---

## What happens

`Gate` accepts NaN and infinite rotation angles, and `Circuit` checks index range but not
type. `probabilities(Circuit(1).rx(float("nan"), 0).measure(0, 0))` returns `{}`, and
`Circuit(2).h(1.0).measure_all()` builds, then crashes inside the simulator with
`TypeError: tuple indices must be integers or slices, not float`.

## What should happen

Both are rejected at construction with a `ValueError` that names the gate or the index,
so every consumer of the IR (simulator, compiler, QASM emitter) gets validated input.
`bool` is not accepted as an index either.

## Reproduction

1. `probabilities(Circuit(1).rx(float("nan"), 0).measure(0, 0))` → `{}`
2. `probabilities(Circuit(2).h(1.0).measure_all())` → `TypeError` from `_apply`

Found by the v0.1 milestone review; defect in 0007.

## Result

Gate rejects non-finite or non-real params and non-integer qubits; Circuit rejects a non-integer qubit count and non-integer measure indices; bool is refused as an index; numpy integers are accepted. All raise ValueError naming the value. The 7 new tests failed before the fix.
