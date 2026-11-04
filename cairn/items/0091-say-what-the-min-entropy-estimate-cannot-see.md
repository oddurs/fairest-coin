---
id: 91
uid: 2b892c17-7f82-4538-93b5-46be83d0a2a6
title: Say what the min-entropy estimate cannot see
type: bug
status: backlog
milestone: v0.3.2
created: 2026-11-04
updated: 2026-11-04
priority: p1
effort: m
area: extract
---

## Problem

Found by the review of v0.3 on 2026-11-04. The guessers past order 16 compare a bit with one earlier bit at most 1,024 back.
Memory that no single earlier bit reveals, or that reaches further back, goes unseen:
`x[i] = x[i-17] ^ x[i-20] ^ Bern(0.05)` scores 0.915 against a true 0.074, so even
half the estimate is about 6× what the source supports; copying from 2,000 back is about
3× over. The code says the 0.5 safety factor "covers every one"; chapter 3 and the 0.3.0
changelog call the estimate conservative. `coin flip` prints ε with no condition. No
estimator that sees only the output can find every structure, so the defect is the claim.
The suite would not notice SAFETY up to 0.78, a narrower confidence bound, halved lag or
order limits, or a constant seed.

## Acceptance criteria

- [ ] extract.py, chapter 3 and the changelog say which structures the estimate can miss, with the parity example
- [ ] `coin flip`, `coin harvest` and chapter 3 state ε as conditional on the estimate
- [ ] Tests pin SAFETY against the worst reviewed overstatement, the confidence bound's width, the lag and order limits (a lag-700 copy, an order-12 source), and that seeds come from `secrets`
