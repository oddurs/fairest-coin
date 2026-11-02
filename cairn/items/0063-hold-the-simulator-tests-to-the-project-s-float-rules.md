---
id: 63
uid: 22528c09-c3cd-4c0b-9a6a-515f930d36d0
title: Hold the simulator tests to the project's float rules
type: bug
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 62
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p1
effort: s
area: sim
---

## What happens

`tests/test_sim.py` compares float probabilities with `==` in about eight places and calls
1e-10 "exact algebra", while `docs/conventions.md` says never compare floats with `==`
and exact algebra uses 1e-12. Chapter 1 tells readers that every test compares with a
stated tolerance, which is currently false.

## What should happen

Every float comparison in the simulator tests uses a named tolerance; `EXACT` is 1e-12;
chapter 1's claim is true, and says what the doctests do differently.

## Reproduction

1. `grep -n '== {' tests/test_sim.py`
2. `grep -n 'EXACT = ' tests/test_*.py`

Found by the v0.1 milestone review; defect in 0009 and 0012.

## 2026-11-01

8 float dict comparisons and state[0] == 1 now use pytest.approx(abs=EXACT); EXACT tightened 1e-10 → 1e-12 to match the rule and test_gates.py. Property tests passed at 1e-12 across 5 fresh hypothesis seeds (400 random circuits each).

## Result

tests/test_sim.py: no bare float == remains; EXACT = 1e-12 with its justification. Chapter 1 now says computed numbers are compared with a tolerance and that its printed examples are the stated exception.
