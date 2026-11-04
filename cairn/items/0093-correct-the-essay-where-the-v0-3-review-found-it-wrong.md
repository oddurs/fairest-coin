---
id: 93
uid: 449f8528-c8f6-43d2-8258-a8fa23961359
title: Correct the essay where the v0.3 review found it wrong
type: docs
status: backlog
milestone: v0.3.2
created: 2026-11-04
updated: 2026-11-04
priority: p2
effort: s
area: essay
---

## Problem

Found by the review of v0.3 on 2026-11-04. Chapter 2 explains the first chip map's sign error with the +0.63% lean measured
on the second map without saying so, and calls that prediction "readout alone" though it
modelled gate noise. Spike 0069 says the readout and coin jobs ran 23 minutes apart; that
is the gap between submissions, and chapter 2 says back to back. The README claims every
example in the chapters is run (a `text` block is not) and that quantum randomness "can
come with a proof" without the loophole caveat. The 0.3.1 changelog says "under 1.3e-5"
for 1.3036e-5.

## Acceptance criteria

- [ ] Each listed sentence matches the archive, checked by recomputation
- [ ] The README's claim about tested examples is true (the `text` block is run, or the claim is narrowed)
