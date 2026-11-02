---
id: 84
uid: 75605429-c390-4df1-9e65-f76974bbc41b
title: Rebuild the v0.4 plan on what v0.2 and v0.3 found
type: chore
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p0
effort: m
area: chsh
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. The v0.4 items predate the hardware findings and some of what certification needs:
- Randomness expansion cannot come out positive with fresh uniform setting bits every round.
- Certified outcome bits still need hashing at the certified min-entropy.
- 5σ on S is not a soundness bound.
- Every round is assumed to behave the same, against drift and switching seen on this chip.
- Qubit pairs are picked from published calibration, which spike 0069 found unreliable.
- The pool is empty, so setting bits need a fresh harvest.
- 0042 sets no tolerance for its prediction.
- 0058 duplicates 0070, 0071's criterion contradicts its proposal, and 0066 (the deprecated
  sampler) belongs before any v0.4 hardware run.

## Acceptance criteria

- [x] Each problem above is addressed in an item's body or criteria, or explicitly ruled out of scope with a reason
- [x] `cairn check` passes and the v0.4 dependency graph is acyclic and complete

## 2026-11-02

Each review finding is addressed in an item: expansion (0043 claims none and reports the net, milestone 0004 rules expansion out with the Pironio numbers), certified bits hashed at the certified rate (0043), soundness (0041 Hoeffding lower bound S_low at ε, used in 0042/0043/0044 and 0004), identical rounds and drift (0040 interleaving, 0042 per-half S, 0047/0049 name the assumption), pair selection from measured readout (0038), fresh harvest needed (0043, QPU with approval), prediction tolerance (0042 interval), freedom of choice with settings in the job (0040, 0049). Housekeeping: 0058 dropped (duplicate of 0070), 0071's proposal now raises SAFETY as its criterion says and names its sources instead of scratch scripts, 0066 moved into v0.4 and 0039 depends on it. cairn check passes; v0.4 has 3 ready items and an acyclic chain to 0048.

## Result

v0.4 rebuilt: no randomness-expansion claim, a Hoeffding lower bound on S at stated ε instead of 5σ, certified bits Toeplitz-hashed at the certified rate, measured readout for pair selection, interleaved settings and per-half S for drift, a prediction interval, a fresh harvest for setting bits, and the remaining assumptions named in chapters 5 and the epilogue. 0058 dropped, 0071 fixed, 0066 moved into v0.4.
