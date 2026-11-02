---
id: 35
uid: 71733a0b-c656-4da7-83e3-283abd37eeef
title: 'Write chapter 3: make it fair'
type: docs
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 33
- 34
created: 2026-11-01
updated: 2026-11-02
closed_at: 2026-11-02
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

- [x] Every number traceable to an archived run
- [x] States the extractor's independence assumption and cites the spike's evidence
- [x] Linked from the README's chapter index

## 2026-11-01

Chapter 3 material from spike 0028: qubit 88. Von Neumann makes its bits pass every fairness test, while a periodic disturbance at 0.489 cycles/shot leaves the output correlated. 'Fair' and 'independent' are different claims. Also qubit 34's telegraph switching between about 52% and 72% tails.

## 2026-11-02

Chapter 3 material from 0032: verifiability against secrecy. Publishing a harvest's raw shots with the extraction seed lets anyone check every flip it produced, and predict every flip it has not produced yet. So the order matters: spend, then publish.

## 2026-11-02

From spike 0069: per-qubit coin bias does not persist (correlation −0.05 between chip maps 4.7 h apart; qubit 59 went 79.8% → 49.8%). Chapter 2's worst misses were readout excursions the calibration recorded afterwards. This is the strongest argument for extraction over prediction: the bias is not a fixed property to correct, so remove it without knowing it. Harvest run 2026-11-02-dbk2ldpffo6c73ban1n0 (qubit 104, 100,000 shots, 44,144 bits pooled) is kept out of git, in the main checkout's data/runs, until its batch is spent; the chapter can spend it as its demonstration, then commit the run.

## 2026-11-02

Evidence: every example in the chapter runs under tests/test_chapters.py, and recomputes its numbers from archived runs (harvest 2026-11-02-dbk2ldpffo6c73ban1n0 with its extraction.json; readout runs dbk2a81k… and dbk2khgn…). Prose numbers not in examples were recomputed from the same runs or quoted from spikes 0028 and 0069. The independence assumption is stated in 'The assumption', with spike 0028's evidence (151/156, qubits 34 and 88). The harvest batch was spent (coin flip --shots 44144: 21,971 heads, 22,173 tails) before its run and extraction.json were committed; recomputation from the archive reproduces those counts exactly. README links the chapter.

## Result

docs/chapters/03-make-it-fair.md: mitigation vs extraction, von Neumann and its independence assumption (spike 0028), the battery, Toeplitz hashing at half the min-entropy estimate (44,144 bits from qubit 104, recomputable from the archive), spend-then-publish, and π passing the battery. Ends on: if tests can't prove randomness, what can?
