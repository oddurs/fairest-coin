---
id: 47
uid: 3c475351-5655-4ab7-9fbe-90705b3800fb
title: 'Write chapter 5: the proof'
type: docs
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 43
- 45
- 46
created: 2026-11-01
updated: 2026-11-06
closed_at: 2026-11-06
priority: p0
effort: m
area: essay
---

## Problem

The climax: Bell's theorem, the CHSH game, and a coin that certifies itself.

## Proposal

`docs/chapters/05-the-proof.md`: CHSH as a game no classical strategy wins more than 75%
of the time, the prediction committed in advance, the measured S, and the bootstrap loop
with its accounting.

## Acceptance criteria

- [x] Links the prediction commit and the result run
- [x] States what this does *not* prove, deferring the full account to the epilogue
- [x] Names the assumptions the certified bits rest on: independent rounds (with the run's own drift check as evidence), settings in the job before it runs, one chip, and no randomness expansion
- [x] Linked from the README's chapter index

## 2026-11-06

docs/chapters/05-the-proof.md: the CHSH game (all sixteen plans tried, best 75%); what the Bell pair does; the argument's two provisos stated where it is made; the prediction committed in c86a39c and the run's commit 6146f58; the result, S = 2.738, S_low = 2.495, with the figure; the coin choosing its own settings (prediction f2a8dc0, read from the committed file), S = 2.761, S_low = 2.582, the certified rate, the accounting (44,000 in, 7,475 out, −36,525) and the first certified flip's receipt, quoted because the run stays private until its batch is spent; then what this does not prove: one chip, settings in the job, independent rounds with both runs' halves as evidence (1.4σ and 1.7σ the same way), the hardware's word, no expansion, deferring to the epilogue. Examples and commands run in tests/test_chapters.py; the receipt and the private run's figures are quoted.

## Result

Chapter 5 written and linked: the CHSH game, two predicted-then-measured runs (S = 2.738 and 2.761), the coin choosing its own settings, the net-negative accounting, and five named assumptions, deferring the full account to the epilogue.
