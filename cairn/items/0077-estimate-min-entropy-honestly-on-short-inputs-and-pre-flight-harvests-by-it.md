---
id: 77
uid: ff51b23c-2dd4-4f7d-a60c-35e30e94b59b
title: Estimate min-entropy honestly on short inputs, and pre-flight harvests by it
type: bug
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p0
effort: s
area: extract
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. `min_entropy` scores lags and orders that have almost no observations, whose upper
bound is then 1, so it returns 0 bits per bit on 1,000 fair bits and only 0.32 at 1,100.
`expected_bits` assumes about a bit per shot, so harvests of roughly 130–1,100 shots pass the
pre-flight, spend QPU time, and extract nothing; the suggested `--from-run` retry fails the
same way. `--from-run` also prints "archived" for a run it did not archive, the planned bit
count overstates the yield, and an ArchiveError from loading the run skips the recovery
message.

## Acceptance criteria

- [x] Each guesser runs only where it has enough guesses to bound: a repeated block scores 0 at every length, and a fair source is never scored 0 (above 0.12 from 200 bits, above 0.35 from 1,000; property tests)
- [x] Harvest refuses, before submitting, any shot count not forecast to yield 1,000 bits, forecasting with the estimator itself on simulated coins at the predicted bias, not an idealised bound
- [x] `--from-run` output does not claim to archive; ArchiveError from extraction carries the recovery message

## 2026-11-02

Criterion 1 restated. The original ('within 0.15 of 1 bit from 2,000 bits') was a guess. A first fix that met something like it did so by switching off the lag and Markov guessers on short inputs, which made a short repeated block look random (0.54 bits/bit): the unsafe direction, caught in review. With each guesser needing 100 of its own guesses, repeated blocks score 0 at every length, and fair sources are honestly uncertain when short: 0.18 at 200 bits, 0.41 at 1,000, 0.55 at 2,000, 0.90 at 100,000 (10 seeds each). Short inputs cannot certify much. The harvest pre-flight now forecasts with the estimator on simulated coins at the predicted bias (worst of 5 seeds) and refuses below 1,000 bits, which keeps harvests clear of the noisy cliff (roughly 3,500 shots minimum). At 100,000 bits nothing changed, so chapter 3's numbers stand.

## Result

min_entropy scores each guesser only on 100+ of its own guesses: repeated blocks score 0 at every length, fair inputs are never 0 (0.41 at 1,000 bits, 0.90 at 100,000, unchanged there). Harvest forecasts its yield with the estimator on simulated coins at the predicted bias (worst of 5) and refuses under 1,000 bits; --from-run no longer claims to archive; any failure after a harvest is archived names the recovery.
