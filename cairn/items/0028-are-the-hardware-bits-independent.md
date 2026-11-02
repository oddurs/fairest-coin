---
id: 28
uid: cc53f04d-e176-4bea-94ee-9275a9abebed
title: Are the hardware bits independent?
type: spike
status: backlog
milestone: v0.3
depends_on:
- 23
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: extract
---

## Question

Do real-hardware bits show correlations: drift across a job, shot-to-shot memory, or
crosstalk between neighbouring qubits in the chip-map run?

## Why it has to be answered before the work

The von Neumann extractor makes biased bits perfectly fair only if they are independent and
identically distributed. If they are not, it gives false confidence, and we need a seeded
extractor such as Toeplitz hashing instead.

## Options

- Bits are i.i.d. enough: von Neumann suffices
- Correlations exist: use a Toeplitz-hashing extractor with a min-entropy estimate

## What would settle it

Autocorrelation at lags 1–100 within a qubit's shot sequence, and the correlation between
neighbouring qubits, on archived runs that keep per-shot memory, with significance stated.

## Answer

<!-- Filled in when the spike closes. -->

## 2026-11-01

The chip-map run keeps per-shot memory for all 156 qubits (data/runs/2026-11-02-dbjuh5d6p51s73cljo60). A first look already shows drift: splitting the 100,000 shots in halves gives a per-qubit z spread of 2.2 where 1.0 is expected, and q29 falls from 68.8% to 65.9% tails across the job.

## 2026-11-01

Correction to the note above: the 2.2 z spread is driven by a few qubits, not the chip. Per qubit (chipmap._drift, halves of the run): 8 of 156 change by more than 3σ where 0.4 are expected; q34 +20.1σ, q89 +10.2σ, q29 −8.0σ, q59 +5.9σ. A robust (MAD) spread is about 1.09. So most qubits look stationary over 25 s, and the extractor question is per qubit.
