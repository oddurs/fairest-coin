---
id: 82
uid: 3ca0d5c9-668d-4b0d-9d66-eaef71a81cb2
title: Bring the essay up to date with what v0.3 found
type: docs
status: backlog
milestone: v0.3.1
depends_on:
- 78
created: 2026-11-02
updated: 2026-11-02
priority: p1
effort: m
area: essay
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02.
- Chapter 3 opens on r = −0.05 between two chip maps, a Pearson value dragged down by a dozen
  outliers: rank correlation is +0.31, and without the outliers +0.24. Its lead example
  (qubit 59) was a readout excursion, not a coin bias.
- Chapter 2 was not updated after spike 0069 answered its questions (qubit 59, the reversed
  sign, the three jobs).
- The README still says `coin flip` only simulates, never mentions harvest, pool or receipts,
  and claims every command in the chapters is tested.
- Chapter 3 and the README promise certification "without trusting the device at all",
  which the plan rules out.
- Smaller slips: "if and only if", "five tests … six", 0.69% for 0.6836%, the first run's
  prediction order. Spike 0069's third answer and one spike 0028 detail are overstated.
- CHANGELOG 0.3.0 has no Changed entry for `coin flip`.

## Acceptance criteria

- [ ] Every number changed or added is recomputed from the archive (examples run under test_chapters)
- [ ] Chapter 2 tells what spike 0069 found; chapter 3's opening rests on the robust statistics
- [ ] The README describes the hardware commands and claims only what the tests check
- [ ] No sentence promises device-independent or loophole-free certification
- [ ] Spikes 0028 and 0069 carry corrections
