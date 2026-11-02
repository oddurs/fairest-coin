---
id: 84
uid: 75605429-c390-4df1-9e65-f76974bbc41b
title: Rebuild the v0.4 plan on what v0.2 and v0.3 found
type: chore
status: backlog
milestone: v0.3.1
created: 2026-11-02
updated: 2026-11-02
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

- [ ] Each problem above is addressed in an item's body or criteria, or explicitly ruled out of scope with a reason
- [ ] `cairn check` passes and the v0.4 dependency graph is acyclic and complete
