---
id: 71
uid: 02202c56-5627-4776-bdf4-3af6a332e169
title: Tighten the min-entropy estimate for hidden-state sources
type: feature
status: backlog
milestone: later
created: 2026-11-01
updated: 2026-11-01
priority: p3
effort: m
area: extract
depends_on:
- 70
---

## Problem

`coin.extract.min_entropy` scores how often its guessers are right on average. Min-entropy
is set by the likeliest sequence, and for sources with hidden state the two differ:
- telegraph switching with short dwell times;
- intermittent alternation;
- a bias cycling with a drifting period.

Review of 0070 found such sources overstated by up to 1.77 times. Extraction covers this
by spending only half the estimate (SAFETY), which wastes about half the output on honest
sources.

## Proposal

Bound the likeliest sequence directly, not the average hit rate:
- a Viterbi or max-cycle bound on fitted order-k models;
- phase guessers fitted in sliding windows, so a drifting period stays in reach;
- the remaining SP 800-90B predictors (MultiMCW, LZ78Y) and the compression estimate.

Then raise SAFETY (spend more of the estimate) only as far as the evidence allows.

## Acceptance criteria

- [ ] On the sources the 0070 reviews built (short-dwell telegraph, drifting-period and chirped bias cycles, intermittent alternation; added as tests), the estimate alone is at most the true value or its proven upper bound
- [ ] SAFETY is raised only by an amount every such test supports, and the change is recorded with the evidence
