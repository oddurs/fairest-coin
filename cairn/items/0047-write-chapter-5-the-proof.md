---
id: 47
uid: 3c475351-5655-4ab7-9fbe-90705b3800fb
title: 'Write chapter 5: the proof'
type: docs
status: backlog
milestone: v0.4
depends_on:
- 43
- 45
- 46
created: 2026-11-01
updated: 2026-11-01
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

- [ ] Links the prediction commit and the result run
- [ ] States what this does *not* prove, deferring the full account to the epilogue
- [ ] Names the assumptions the certified bits rest on: independent rounds (with the run's own drift check as evidence), settings in the job before it runs, one chip, and no randomness expansion
- [ ] Linked from the README's chapter index
