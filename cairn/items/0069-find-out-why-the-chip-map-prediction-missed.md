---
id: 69
uid: f0e32a13-8a2b-4825-9be5-e090faac8d93
title: Find out why the chip-map prediction missed
type: spike
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 23
created: 2026-11-01
updated: 2026-11-02
closed_at: 2026-11-02
priority: p1
effort: s
area: noise
qpu: true
---

## Question

The chip-map run (data/runs/2026-11-02-dbjuh5d6p51s73cljo60) put 31 of 150 qubits within 3σ
of a prediction built from that hour's published calibration, with no per-qubit correlation
between predicted and observed bias. Is the miss in the readout calibration, in state
preparation, or in drift?

## Why it has to be answered before the work

Chapter 2 can only offer candidates. Readout mitigation (0029) assumes a trustworthy
confusion matrix, and chapter 3 needs to know whether the bias it removes is stable.

## Options

- The published readout numbers do not describe readout during a simultaneous 156-qubit
  measurement (crosstalk, or a different calibration protocol)
- Coherent gate error: an over- or under-rotated `sx` biases the coin directly, and
  randomized benchmarking's `gate_error` does not carry the sign
- Drift: the qubits changed between calibration and run, and within the run
- Two-level-system defects on a few qubits (q59 at 79.8% tails)

## What would settle it

One job, three circuits on every qubit in parallel, run back to back: prepare |0⟩ and
measure, prepare |1⟩ and measure, and the coin. The first two measure readout under the
coin's own conditions; the coin's residual after that readout is state preparation. Repeat
the coin a second time in the same job to separate drift from bias. Estimate the cost with
`coin run chip-map --dry-run`-style arithmetic and get the owner's approval first.

## Answer

**Three causes. None of them is visible in the published calibration, and the third makes
per-qubit prediction hopeless.** Evidence:
- `analysis/readout_vs_coin.py` on three back-to-back jobs on ibm_marrakesh:
  - prepare |0⟩, 20,000 shots: `2026-11-02-dbk2a81kdqps7391ka9g`;
  - prepare |1⟩, 20,000 shots: `2026-11-02-dbk2khgnceqs73al2ojg`;
  - a fresh chip map, 100,000 shots: `2026-11-02-dbk2l21kdqps7391l420`;
- `coin compare` on the new chip map, and on the old one,
  `2026-11-02-dbjuh5d6p51s73cljo60`.

1. **Readout excursions caused the worst misses.**
   - Qubits 59, 29, 48 and 34 came up 65–80% tails in the first chip map.
   - The next published calibration recorded broken readout on 34, 48 and 59, with p(1|0)
     of 0.56–0.75. Qubit 59's published (0.747, 0.188) predicts a 78.0% coin; it measured
     79.8%.
   - 4.7 hours later the readout had recovered: measured p(1|0) was 0.000, 0.025 and 0.066.
     Their coins read 51.0%, 49.2% and 49.8%.
   - The calibration describes a readout from some other time. Across the chip, published
     p(1|0) correlates with measured at only +0.46, and p(0|1) at +0.89. 21 of 156 qubits
     read prepared |0⟩ within 3σ of their published error, and 38 of 156 read prepared |1⟩.
2. **A chip-wide state-preparation lean explains the sign.**
   - With the measured readout undone, the coin before measurement leans tails: median
     +0.63%, median |bias| 0.67%. Only 58 of 155 qubits are fair within 3σ.
   - A coherent sx over-rotation within each qubit's published gate error covers 144 of 147
     (median bound ±2.53%).
   - Readout pulls the coin toward heads, and preparation pushes it further toward tails.
     That is why chapter 2 predicted −0.45% and measured +0.45%.
3. **The large leans come and go over hours.**
   - Measured coin bias in the two chip maps, 4.7 hours apart: rank correlation +0.31, and
     +0.24 for the 144 qubits within 5% of fair in both, so ordinary leans partly persist.
     The large ones do not: the plain correlation, dominated by them, is −0.05, and new
     outliers appeared (qubit 90 at +9.1%, 85 at +5.6%). (Corrected after the v0.1–v0.3
     review; this first read only the −0.05.)
   - Even with readout measured in the same session (23 minutes before the coin, because
     of queueing), the readout-only model put 59 of 156 coins within 3σ. With published
     readout, the same coin run scored 44 of 147.

**Consequence.** No calibration, published or measured, predicts an individual qubit's coin
to better than about a percent for longer than it holds still. So the project stops
predicting bias and removes it (chapter 3).

**Caveats.**
- The readout jobs and the coin ran 23 minutes apart, so the measured-readout comparison
  mixes readout error with drift.
- The coherent-error bound shows that coherence *could* explain the state-preparation lean,
  not that it does. An error-amplification circuit (sx repeated 4k+1 times) would test it
  directly, and is left for later.

## 2026-11-01

A later calibration (owner's dry run, 2026-11-02 ~02:53 UTC, not archived) newly flags qubits 34, 48 and 59 as readout-broken: p(1|0) = 0.56, 0.65 and 0.75. In the chip-map run they came up tails 65.2%, 64.9% and 79.8%, among the worst misses. So for these three the miss was most likely readout that went bad before the calibration caught it, not state preparation. The spike's prepare-|0⟩ circuit tests exactly this; archive a fresh calibration with it.

## 2026-11-01

From spike 0028: coupled qubits 113 and 119, both excluded by the calibration model, are anticorrelated at −123σ (r ≈ −0.39) in the same shot. No other coupled pair shows crosstalk. Worth one line in the spike's readout circuits.

## 2026-11-02

Tooling built: coin run readout --backend --shots N --prepare {0,1} (--dry-run|--submit), predicted from each qubit's published readout straight from the snapshot (so qubits the model excludes, including the broken-readout ones, are tested too); readout.measured(run0, run1) gives per-qubit Readout as the jobs saw it. Deviation from the plan: three back-to-back jobs (prepare 0, prepare 1, a fresh chip map), not one job, because the adapter and the archive hold one circuit per job; drift between jobs is a caveat, drift within each job is still measurable. Proposed budget: 20,000 shots per readout job (~7 s each) and 100,000 for the chip map (~27 s).

## Result

Three causes: transient readout excursions (34/48/59 read 56–75% p(1|0) in the published calibration, recovered to 0–7% hours later); a chip-wide state-preparation tails lean of +0.63% median once measured readout is undone, within the coherent sx bound on 144/147 qubits; and large per-qubit leans that come and go within hours (ordinary leans partly persist: rank correlation +0.31 over 4.7 h, though the plain correlation is −0.05). Published readout correlates with measured at +0.46 (p(1|0)). Prediction of a single qubit's bias is not achievable; extraction is.

## 2026-11-02

Correction (review of v0.1–v0.3): conclusion 3 is overstated. The −0.05 between the two chip maps is a Pearson correlation dominated by a dozen outliers; rank correlation is +0.31 (p ≈ 1e-4), and the 144 qubits within 5% of fair in both maps correlate at +0.24. Ordinary per-qubit leans partly persist; the large excursions are what come and go. Also, qubit 59's later published readout predicts 78.0% (0.7798), not 77.9%. Chapters 2 and 3 now say this, with the numbers computed in tested examples.
