---
id: 77
uid: ff51b23c-2dd4-4f7d-a60c-35e30e94b59b
title: Estimate min-entropy honestly on short inputs, and pre-flight harvests by it
type: bug
status: backlog
milestone: v0.3.1
created: 2026-11-02
updated: 2026-11-02
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

- [ ] Each guesser runs only where it has enough observations to bound; a fair source's estimate is within 0.15 of 1 bit from 2,000 bits up and never 0 above the minimum (property test)
- [ ] Harvest refuses, before submitting, any shot count whose extraction would yield nothing, using the estimator's own behaviour on a fair source, not an idealised bound
- [ ] `--from-run` output does not claim to archive; ArchiveError from extraction carries the recovery message
