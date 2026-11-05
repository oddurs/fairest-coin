---
id: 45
uid: c5a6a221-8d1a-4854-b36a-b5e94007e643
title: Draw the correlations and S against its bounds
type: feature
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 24
- 42
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
priority: p2
effort: s
area: figures
---

## Problem

Chapters 4 and 5 need the agreement of the Bell pair and S shown against the classical
bound of 2 and Tsirelson's bound of 2√2.

## Proposal

The correlation for each setting pair, and S with its error bar against the predicted S
and both bounds.

## Acceptance criteria

- [x] Generated from archived runs by the figure pipeline
- [x] Both bounds are drawn and labelled

## 2026-11-05

docs/figures/chsh.svg, rendered by figures.chsh_test from 0042's run (2026-11-05-dbmfqed8ft8s738upl80) through the existing byte-reproducible pipeline: left, each setting's correlation measured (1σ) against predicted; right, S = 2.738 ± 0.027 with S_low = 2.495, the committed 95% interval [2.713, 2.815], and the classical bound 2 and Tsirelson's 2√2 drawn and labelled; the footer names the commit the prediction was in (c86a39c). Checked by eye as a raster, and by a test that pins the numbers and both labels.

## Result

docs/figures/chsh.svg, from the archived CHSH run: each correlation against prediction, and S, S_low and the committed interval against the classical bound 2 and Tsirelson's 2√2, both drawn and labelled.
