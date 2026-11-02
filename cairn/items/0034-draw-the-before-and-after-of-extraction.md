---
id: 34
uid: 970e4a0e-4b6b-47e7-bf08-d227e9db0389
title: Draw the before-and-after of extraction
type: feature
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 24
- 31
- 32
created: 2026-11-01
updated: 2026-11-02
closed_at: 2026-11-02
priority: p2
effort: s
area: figures
---

## Problem

Chapter 3 needs to show the coin made fair.

## Proposal

Bias before and after extraction with error bars, and battery p-values for raw versus
extracted bits from the same run.

## Acceptance criteria

- [x] Generated from archived runs by the figure pipeline
- [x] The significance threshold is drawn and labelled

## 2026-11-02

docs/figures/extraction.svg, rendered by coin.figures.extraction from the committed chip map data/runs/2026-11-02-dbjuh5d6p51s73cljo60 (not the harvest run, which stays out of git until its batch is spent). Battery p-values (log₁₀, floored at 1e-30, rounded to two places so libm differences across platforms cannot change the bytes) for raw shots, von Neumann and Toeplitz (fixed seed) on qubits 88 and 34, with the α = 0.01 threshold drawn and labelled. Tests pin the label and the archived bit counts; scripts/figures --check passes.

## Result

docs/figures/extraction.svg: the battery before and after extraction on chip-map qubits 88 and 34. Qubit 88: von Neumann passes the frequency tests and fails runs/serial; Toeplitz passes all six. Qubit 34: raw fails everything, both extractors pass.
