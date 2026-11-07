---
id: 4
uid: 0adb1d33-8e79-4d01-956f-447b680f29e1
key: v0.4
title: The certified coin
type: milestone
status: done
created: 2026-11-01
updated: 2026-11-06
closed_at: 2026-11-06
priority: p2
due: 2026-12-27
---

## Ships

A Bell test run on real hardware, with the measurement settings chosen by the v0.3 coin,
violates the CHSH bound, and every bit `coin flip` hands out carries that batch's S value.
Chapters 4 and 5.

## Done when

- [x] Two-qubit circuits are lowered to the backend's native gates by our own compiler
- [x] The predicted S, with the interval it is judged against, is committed to git before the hardware run that measures it
- [x] A one-sided lower confidence bound on S, at a stated ε over the run's rounds, exceeds 2, or chapter 5 explains why not
- [x] The randomness accounting is explicit: setting bits in, certified bits out (hashed at the certified min-entropy), and the net, which is negative with uniform settings
- [x] Tagged `v0.4.0`

## Explicitly not in this milestone

- Any claim of loophole-free certification
- Randomness expansion: with fresh uniform settings every round the accounting is net negative
  (0.27 certified bits per round at S = 2.5, for 2 setting bits in). Spot-checking protocols
  that can come out positive are left for later.

## 2026-11-06

Shipped as v0.4.0 on d390172. (1) coin.compile lowers cx to one native cz (0037). (2) Both CHSH predictions, with their intervals, were on main before their runs: c86a39c (#80) for S = 2.738, f2a8dc0 (#86) for S = 2.761; c86a39c is an ancestor of the result on main. (3) S_low = 2.495 and 2.582 at ε = 2⁻³². (4) 44,000 setting bits in, 7,475 certified bits out at 0.343 bits a round, net −36,525 (0043, chapter 5). (5) Tagged. The certified run and its harvest join the archive when their batches are spent.

## Result

v0.4.0 released: the CHSH test predicted in public first and measured on ibm_marrakesh (S = 2.761 ± 0.020, S_low = 2.582 at ε = 2⁻³²), settings chosen by the coin's own bits, 7,475 certified bits at a net loss of 36,525, and receipts that carry S.
