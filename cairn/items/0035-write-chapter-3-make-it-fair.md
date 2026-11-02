---
id: 35
uid: 71733a0b-c656-4da7-83e3-283abd37eeef
title: 'Write chapter 3: make it fair'
type: docs
status: backlog
milestone: v0.3
depends_on:
- 33
- 34
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: essay
---

## Problem

The coin is made fair, and then the chapter must admit that no test can prove it.

## Proposal

`docs/chapters/03-make-it-fair.md`: mitigation against extraction, von Neumann's trick,
the independence result, the battery, and the π punchline. End on "if tests can't prove
randomness, what can?"

## Acceptance criteria

- [ ] Every number traceable to an archived run
- [ ] States the extractor's independence assumption and cites the spike's evidence
- [ ] Linked from the README's chapter index

## 2026-11-01

Chapter 3 material from spike 0028: qubit 88. Von Neumann makes its bits pass every fairness test, while a periodic disturbance at 0.489 cycles/shot leaves the output correlated. 'Fair' and 'independent' are different claims. Also qubit 34's telegraph switching between about 52% and 72% tails.
