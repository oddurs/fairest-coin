---
id: 4
uid: 0adb1d33-8e79-4d01-956f-447b680f29e1
key: v0.4
title: The certified coin
type: milestone
status: backlog
created: 2026-11-01
updated: 2026-11-01
priority: p2
due: 2026-12-27
---

## Ships

A Bell test run on real hardware, with the measurement settings chosen by the v0.3 coin,
violates the CHSH bound, and every bit `coin flip` hands out carries that batch's S value.
Chapters 4 and 5.

## Done when

- [ ] Two-qubit circuits are lowered to the backend's native gates by our own compiler
- [ ] The predicted S, with the interval it is judged against, is committed to git before the hardware run that measures it
- [ ] A one-sided lower confidence bound on S, at a stated ε over the run's rounds, exceeds 2, or chapter 5 explains why not
- [ ] The randomness accounting is explicit: setting bits in, certified bits out (hashed at the certified min-entropy), and the net, which is negative with uniform settings
- [ ] Tagged `v0.4.0`

## Explicitly not in this milestone

- Any claim of loophole-free certification
- Randomness expansion: with fresh uniform settings every round the accounting is net negative
  (0.27 certified bits per round at S = 2.5, for 2 setting bits in). Spot-checking protocols
  that can come out positive are left for later.
