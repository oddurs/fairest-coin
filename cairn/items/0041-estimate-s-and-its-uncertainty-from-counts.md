---
id: 41
uid: 9da3b9d4-07e4-427a-b973-329918951f9f
title: Estimate S and its uncertainty from counts
type: feature
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 16
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
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

- [x] An ideal simulated Bell pair gives S = 2√2 within sampling error
- [x] A depolarized pair with visibility V gives S = 2√2·V, tested for several V
- [x] A local hidden-variable model in the tests never exceeds 2 beyond sampling error
- [x] Over many simulated local runs, S_low exceeds 2 in no more than an ε fraction (tested at a loose ε)

## 2026-11-05

chsh.estimate(counts) gives S from the four correlations, its standard error (each E binomial, variance (1 − E²)/n, the four independent), and the CHSH game's tally: a round is won when the bits agree, except at settings (1, 1) where they must differ. Estimate.lower_bound(ε) = 8(ŵ − √(ln(1/ε)/2n)) − 4 from the pooled win rate, which stays right when per-shot random settings leave unequal counts per setting. Tests: an ideal simulated pair gives 2√2 within 4σ at 20,000 shots per setting; depolarized pairs give 2√2·V for V = 0.95, 0.8, 0.6, 0.3; random mixtures of the sixteen deterministic local strategies and the best one alone never exceed 2 beyond 4σ (the best gives exactly 2, σ = 0); 400 local runs of 2,000 rounds put S_low above 2 at ε = 0.1 in at most a tenth (Hoeffding: in practice none); S_low pinned on a hand case. 200,000 ideal rounds clear 2 at ε = 2⁻³². The module keeps its own sign convention (minus on E(a₁, b₁)), equivalent to the item's. Six mutants replayed, all killed.

## Result

chsh.estimate gives S, its standard error, and Estimate.lower_bound(ε), a Hoeffding bound on the CHSH win rate that assumes only independent rounds and uniform settings; tested on ideal, depolarized and local-hidden-variable models, with S_low exceeding 2 for a local model in no more than an ε fraction of runs.
