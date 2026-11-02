---
id: 82
uid: 3ca0d5c9-668d-4b0d-9d66-eaef71a81cb2
title: Bring the essay up to date with what v0.3 found
type: docs
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
depends_on:
- 78
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
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

- [x] Every number changed or added is recomputed from the archive (examples run under test_chapters)
- [x] Chapter 2 tells what spike 0069 found; chapter 3's opening rests on the robust statistics
- [x] The README describes the hardware commands and claims only what the tests check
- [x] No sentence promises device-independent or loophole-free certification
- [x] Spikes 0028 and 0069 carry corrections

## 2026-11-02

Chapter 3 now opens on the robust statistics (rank correlation +0.31; +0.24 without the twelve large leans; −0.05 plain), computed in a tested example, and its lead example is what spike 0069 found for qubit 59. Chapter 2 tells what 0069 found (qubit 59's readout excursion, recomputed in an example: published 0.747/0.188 → 78.0%, measured 0.066/0.069; and the +0.63% preparation lean behind the reversed sign, also an example), fixes 0.69% → 0.68% and the first run's prediction order (the dry run, six minutes earlier). Chapter 3: 'if and only if' → a guarantee only, 'six p-values' explained, certification promise toned to what chapter 5 can claim. README: hardware commands (harvest, pool, flip, publish, recover), the tested-claim narrowed to Python examples and coin commands, certification wording. Spikes 0028 and 0069 corrected (answer text and notes; 0069's 77.9% → 78.0%). CHANGELOG 0.3.0 gets its Changed entry.

## Result

The essay matches the archive and the later spikes: chapter 3's opening rests on robust statistics, chapter 2 tells what spike 0069 found, the README describes the hardware commands and claims only what is tested, and nothing promises loophole-free certification. Spikes 0028 and 0069 corrected.
