---
id: 28
uid: cc53f04d-e176-4bea-94ee-9275a9abebed
title: Are the hardware bits independent?
type: spike
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 23
created: 2026-11-01
updated: 2026-11-02
closed_at: 2026-11-01
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

**Mostly yes, and the exceptions are exactly the case the spike worried about.**
`uv run python analysis/independence.py data/runs/2026-11-02-dbjuh5d6p51s73cljo60`
(156 qubits × 100,000 shots); the method is checked on synthetic bits in
`tests/test_independence.py`.

- **151 of 156 qubits are independent to this run's resolution.**
  - Their 15,100 (qubit, lag) autocorrelations at lags 1–100 have a spread of 1.005, with
    none beyond 4σ (1.0 expected).
  - Lag 1 alone: none beyond 3σ (0.4 expected).
  - Resolution: |r| ≈ 0.013 at any lag would have shown.
- **Five qubits have time structure.** Each is flagged by Ljung-Box or by lag 1, at 5%
  Bonferroni over the qubits, and each has a recognisable shape:
  - 34: telegraph switching. Its tails rate jumps between about 52% and 72% across
    5,000-shot blocks; Q p < 1e-300.
  - 88: a sharp periodic line at 0.48917 cycles/shot, 822× the mean power. Its
    autocorrelation alternates sign undamped out to lag 100.
  - 36: a line at 0.3319 cycles/shot, 107×.
  - 48: short memory, decaying over about 20 shots; lag 1 +5.8σ.
  - 59: slow wander, plus lag 1 +4.6σ.
  
  Blocking at 5,000 shots removes slow drift but leaves 34, 88, 48 and 36 flagged, so their
  structure is fast; 59 also stays flagged there, by its lag-1 test (+4.1σ), though not by
  Ljung-Box.
- **Crosstalk:** none between coupled neighbours, except 113–119.
  - The other 175 coupled pairs: spread 1.013, none beyond 3σ (0.5 expected).
  - The 11,914 uncoupled pairs, as the control: spread 1.016, none past Bonferroni.
  - 113–119 is anticorrelated at −123σ (r ≈ −0.39); both qubits are already excluded by
    the calibration model.
- **Von Neumann.** On each qubit's own shots its output is fair on all 156 qubits (spread
  0.996; none past Bonferroni). But on qubit 88 the output bits are correlated with each
  other, at +9.8σ at lag 1. The periodic disturbance biases each pair one way or the other
  as its phase drifts against the pairing, and the biases average out. Fairness tests
  pass; the bits are not independent. This is the false confidence the spike asked about,
  observed on hardware.

**Decision.**
- Von Neumann stays as chapter 3's extractor, because it is the lesson. It is only
  applied to bits from qubits that pass this screen on the same run.
- The entropy pool (0032) does not assume i.i.d. bits. It extracts with Toeplitz hashing
  from a conservative min-entropy estimate (new item 0070).
- The test battery (0031) must catch qubit 88's von Neumann output, which makes a real
  negative control.

**Caveats.**
- The memory is assumed to be in execution order. The drift across halves, and the
  telegraph switching of qubit 34, would not survive a shuffle.
- One run, one backend, 25 seconds: which qubits misbehave will change between runs, so
  the screen has to run per batch, not once.

## 2026-11-01

The chip-map run keeps per-shot memory for all 156 qubits (data/runs/2026-11-02-dbjuh5d6p51s73cljo60). A first look already shows drift: splitting the 100,000 shots in halves gives a per-qubit z spread of 2.2 where 1.0 is expected, and q29 falls from 68.8% to 65.9% tails across the job.

## 2026-11-01

Correction to the note above: the 2.2 z spread is driven by a few qubits, not the chip. Per qubit (chipmap._drift, halves of the run): 8 of 156 change by more than 3σ where 0.4 are expected; q34 +20.1σ, q89 +10.2σ, q29 −8.0σ, q59 +5.9σ. A robust (MAD) spread is about 1.09. So most qubits look stationary over 25 s, and the extractor question is per qubit.

## Result

151 of 156 chip-map qubits are independent to resolution |r|≈0.013 (lags 1–100) with no crosstalk; 5 have time structure (telegraph 34, periodic lines 88 and 36, short memory 48, wander 59). Von Neumann's output was fair on all 156 but serially correlated on qubit 88 (+9.8σ). Decision: von Neumann stays as chapter 3's teaching extractor, applied only to screened qubits; the entropy pool uses Toeplitz hashing from a min-entropy estimate (0070). Method: analysis/independence.py, checked by tests/test_independence.py.

## 2026-11-02

Correction (review of v0.1–v0.3): within 5,000-shot blocks qubit 59 is also flagged, by its lag-1 test (+4.1σ) though not by Ljung-Box; the answer said only 34, 88, 48 and 36. The whole-run lag-1 for 48 is +6.0σ; +5.8σ is its within-block value.
