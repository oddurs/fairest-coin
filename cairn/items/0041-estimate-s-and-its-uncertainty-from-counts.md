---
id: 41
uid: 9da3b9d4-07e4-427a-b973-329918951f9f
title: Estimate S and its uncertainty from counts
type: feature
status: backlog
milestone: v0.4
depends_on:
- 16
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: chsh
---

## Problem

The certification is one number and its error bar. Both must be right.

## Proposal

`coin/chsh.py`: correlators E(a,b) from counts per setting pair, S = E(a,b) − E(a,b′) +
E(a′,b) + E(a′,b′), its standard error, and the number of standard deviations above the
local bound of 2.

## Acceptance criteria

- [ ] An ideal simulated Bell pair gives S = 2√2 within sampling error
- [ ] A depolarized pair with visibility V gives S = 2√2·V, tested for several V
- [ ] A local hidden-variable model in the tests never exceeds 2 beyond sampling error
