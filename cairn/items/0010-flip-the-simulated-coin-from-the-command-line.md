---
id: 10
uid: 6b718f47-e1a4-4f0c-b6c6-6db79dead7c3
title: Flip the simulated coin from the command line
type: feature
status: backlog
milestone: v0.1
depends_on:
- 9
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: cli
---

## Problem

v0.1 has to be usable by someone who will never import the library.

## Proposal

`coin flip --sim` runs H + measure on the statevector simulator and prints `HEADS` (0)
or `TAILS` (1). `--shots N` prints counts and the fraction of heads instead. `--seed S`
makes it reproducible. Without `--sim` it exits 2 explaining that hardware arrives in
v0.2, so the flag stays meaningful later.

## Acceptance criteria

- [ ] `coin flip --sim` prints exactly one of HEADS / TAILS and exits 0
- [ ] `coin flip --sim --shots 10000 --seed 1` output is pinned by a snapshot test
- [ ] `coin flip` without `--sim` exits 2 with a message naming `--sim`
- [ ] `coin --help` and `coin flip --help` describe every flag
