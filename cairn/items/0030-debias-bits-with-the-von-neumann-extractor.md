---
id: 30
uid: 7506723c-f012-4600-b246-a95ab65f466c
title: Debias bits with the von Neumann extractor
type: feature
status: backlog
milestone: v0.3
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: extract
---

## Problem

A biased coin can be made perfectly fair: flip twice, keep 01 as 0 and 10 as 1, discard
00 and 11. It costs throughput, at p(1−p) output bits per input bit.

## Proposal

`coin/extract.py`: `von_neumann(bits) -> bits`, plus the iterated Peres variant that
recovers some of the discarded entropy. Both are pure functions over numpy bit arrays.

## Acceptance criteria

- [ ] Property test: on i.i.d. input of any bias, output is unbiased within 4σ over 10⁶ bits
- [ ] Output yield matches p(1−p) within sampling error
- [ ] Peres yields strictly more bits than single-pass von Neumann on the same input
