---
id: 31
uid: 37f20150-c6d8-4342-8e08-9807278e694b
title: Build a randomness test battery from scratch
type: feature
status: backlog
milestone: v0.3
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: extract
---

## Problem

We need to show that raw bits fail where the bias says they should, that extracted bits
pass, and that passing proves nothing.

## Proposal

`coin/tests_random.py`: frequency (monobit), block frequency, runs, longest run of ones,
and serial tests after NIST SP 800-22, each returning a p-value. Implemented from the
specification using only `math` and numpy, since writing them is the lesson.

## Acceptance criteria

- [ ] Each test reproduces the worked example in NIST SP 800-22 to the published p-value
- [ ] A bias of 0.51 over 10⁶ bits fails monobit; the same bits after von Neumann pass
- [ ] Digits of π, which are deterministic, pass the battery, and a test documents it as the punchline

## 2026-11-01

Negative control from spike 0028: von Neumann applied to qubit 88's shots in data/runs/2026-11-02-dbjuh5d6p51s73cljo60 gives about 25,000 bits that are fair but serially correlated (+9.8σ at lag 1). The serial test should fail them; the monobit test will pass them.
