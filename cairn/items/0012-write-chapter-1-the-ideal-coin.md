---
id: 12
uid: 6bfa605d-e3fc-411d-8077-348cacb388ea
title: 'Write chapter 1: the ideal coin'
type: docs
status: backlog
milestone: v0.1
depends_on:
- 9
- 10
- 11
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: essay
---

## Problem

The reader needs to see a quantum coin built from nothing: what a qubit is, what H does,
why measurement gives 50/50.

## Proposal

`docs/chapters/01-the-ideal-coin.md`. Amplitudes, the Born rule, H as a rotation, and a
walk through `coin/sim.py` itself: the code is the explanation. End by running
`coin flip --sim --shots 10000` and noting that a simulator's randomness is a seeded PRNG,
which is the very thing chapter 0 distrusted.

## Acceptance criteria

- [ ] Every code excerpt is taken from the repository and is checked by a test so it cannot drift
- [ ] Every command shown runs and prints what the chapter says it prints
- [ ] States plainly that the simulated coin is not random, which motivates chapter 2
- [ ] Linked from the README's chapter index
