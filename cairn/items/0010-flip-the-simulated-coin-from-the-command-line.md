---
id: 10
uid: 6b718f47-e1a4-4f0c-b6c6-6db79dead7c3
title: Flip the simulated coin from the command line
type: feature
status: done
milestone: v0.1
assignee: Oddur Sigurdsson
depends_on:
- 9
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] `coin flip --sim` prints exactly one of HEADS / TAILS and exits 0
- [x] `coin flip --sim --shots 10000 --seed 1` output is pinned by a snapshot test
- [x] `coin flip` without `--sim` exits 2 with a message naming `--sim`
- [x] `coin --help` and `coin flip --help` describe every flag

## 2026-11-01

Self-review found --seed -1 crashed with a numpy ValueError traceback; seeds are now validated as non-negative, with a test. Output format pinned: '<face>  <count right-aligned, thousands separators>  <percent, 7.2%>'.

## Result

coin flip --sim prints HEADS or TAILS (exit 0); --shots N prints 'heads  N  P%' and 'tails  N  P%' lines; --seed S (S ≥ 0) replays. 'coin flip --sim --shots 10000 --seed 1' prints 'heads   4,971   49.71%' / 'tails   5,029   50.29%', pinned by a test. Without --sim exits 2 naming --sim. coin.cli.COIN is the coin circuit; FACES maps '0'→heads, '1'→tails.
