---
id: 12
uid: 6bfa605d-e3fc-411d-8077-348cacb388ea
title: 'Write chapter 1: the ideal coin'
type: docs
status: done
milestone: v0.1
assignee: Oddur Sigurdsson
depends_on:
- 9
- 10
- 11
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: m
area: essay
---

## Problem

The reader needs to see a quantum coin built from nothing: what a qubit is, what H does,
why measurement gives 50/50.

## Proposal

`docs/chapters/01-the-ideal-coin.md`. Amplitudes, the Born rule, H as a rotation, and a
walk through `coin/sim.py` itself: the code is the explanation. End by running
`coin flip --sim --shots 10000` and noting that a simulator's randomness is a seeded PRNG,
which is the very thing chapter 0 distrusted.

## Acceptance criteria

- [x] Every code excerpt is taken from the repository and is checked by a test so it cannot drift
- [x] Every command shown runs and prints what the chapter says it prints
- [x] States plainly that the simulated coin is not random, which motivates chapter 2
- [x] Linked from the README's chapter index

## 2026-11-01

Drift guard is tests/test_chapters.py, generic for every chapter: pycon blocks run as one doctest session; python blocks marked <!-- from: PATH --> must appear verbatim in PATH; console blocks run 'coin ...' and compare stdout. Each guard was shown to fail on a deliberate break (output, interference result, excerpt, CLI output). First attempt fed whole Markdown to doctest, which read closing fences as expected output.

## Result

docs/chapters/01-the-ideal-coin.md (~950 words, 16 runnable examples): amplitudes, Born rule, H, interference (H·H = I, which probabilities alone cannot do), circuits, little-endian axes via an excerpt of sim._apply, sampling, the pinned 'coin flip --sim --shots 10000 --seed 1' output with its 1σ = 50 explanation; ends: the simulator's flips are a seeded PRNG, so chapter 2 needs real hardware. tests/test_chapters.py checks every chapter's examples, excerpts and commands.
