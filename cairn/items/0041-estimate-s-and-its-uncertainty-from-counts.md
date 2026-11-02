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
E(a′,b) + E(a′,b′), its standard error, and a one-sided lower confidence bound on S at a
stated ε. Standard errors are not a soundness bound: the bound comes from the CHSH game's
per-round win indicator (w = 1/2 + S/8 for uniform settings) with Hoeffding's inequality
over the n rounds, S_low = 8(ŵ − √(ln(1/ε)/2n)) − 4, which assumes nothing about the
rounds' distribution beyond their being independent.

## Acceptance criteria

- [ ] An ideal simulated Bell pair gives S = 2√2 within sampling error
- [ ] A depolarized pair with visibility V gives S = 2√2·V, tested for several V
- [ ] A local hidden-variable model in the tests never exceeds 2 beyond sampling error
- [ ] Over many simulated local runs, S_low exceeds 2 in no more than an ε fraction (tested at a loose ε)
