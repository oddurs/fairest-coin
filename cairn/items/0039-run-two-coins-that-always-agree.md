---
id: 39
uid: 34f5ccb7-8113-4ef5-aed5-c468e8892e4d
title: Run two coins that always agree
type: feature
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 66
- 22
- 38
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
priority: p1
effort: s
area: chsh
qpu: 'true'
---

## Problem

Before the proof comes the phenomenon: two qubits whose outcomes are each random but
always equal.

## Proposal

`coin run bell --backend NAME`: prepare Φ⁺ on the selected pair, measure both in Z,
predict the agreement rate first, then run and archive.

## Acceptance criteria

- [x] Prediction written before submission, as for every run
- [x] Archived run reports the agreement rate and each qubit's marginal bias
- [x] `--dry-run` shows the lowered circuit and cost

## 2026-11-05

First hardware run 2026-11-05 (owner): data/runs/2026-11-05-dbme92m74qds73ds595g, ibm_marrakesh pair 5-6 (best predicted S = 2.782 on published readout), 10,000 shots, 5 QPU s charged. Counts 00: 4,883, 11: 4,884, 01: 196, 10: 37. Agreement 97.67% against 99.25% predicted (z = −18.2): the model is optimistic. Each coin alone is fair as predicted (P(1) 50.80% on 5, z = +1.6; 49.21% on 6, z = −0.8). The disagreement is lopsided: '01' (5 read 1, 6 read 0) 196 times against '10' 37 times, so qubit 6 loses a 1 in about 3.9% of the shots where both should read 1, while its published p(0|1) is 0.78% (and qubit 6's published p(1|0) is exactly 0). That is readout (or decay just before it), not entanglement: spike 0069's finding that published readout is a poor guide, again. 0042 must predict from readout measured in the same session. An earlier submit (same day) was refused before any job existed: the adapter's circuit-change check compared the flat instruction list, and transpiling lists gates on different qubits in its own order; it now compares each wire's instructions in order (ibm._by_wire), with a regression test on FakeMarrakesh's layout that fails on the old check.

## Result

coin run bell predicts, runs and archives the Bell pair on the best-ranked pair; on ibm_marrakesh 5-6 the two coins agreed 97.67% of 10,000 shots against 99.25% predicted, each fair alone; the miss is qubit 6 losing a 1 far more often than its published readout says, so the CHSH run needs measured readout.
