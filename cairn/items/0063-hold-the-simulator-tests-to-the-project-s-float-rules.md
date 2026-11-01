---
id: 63
uid: 22528c09-c3cd-4c0b-9a6a-515f930d36d0
title: Hold the simulator tests to the project's float rules
type: bug
status: backlog
milestone: v0.2
depends_on:
- 62
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: sim
---

## What happens

`tests/test_sim.py` compares float probabilities with `==` in about eight places and calls
1e-10 "exact algebra", while `.claude/rules/physics.md` says never compare floats with `==`
and exact algebra uses 1e-12. Chapter 1 tells readers that every test compares with a
stated tolerance, which is currently false.

## What should happen

Every float comparison in the simulator tests uses a named tolerance; `EXACT` is 1e-12;
chapter 1's claim is true, and says what the doctests do differently.

## Reproduction

1. `grep -n '== {' tests/test_sim.py`
2. `grep -n 'EXACT = ' tests/test_*.py`

Found by the v0.1 milestone review; defect in 0009 and 0012.
