---
id: 39
uid: 34f5ccb7-8113-4ef5-aed5-c468e8892e4d
title: Run two coins that always agree
type: feature
status: backlog
milestone: v0.4
depends_on:
- 22
- 38
created: 2026-11-01
updated: 2026-11-01
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

- [ ] Prediction written before submission, as for every run
- [ ] Archived run reports the agreement rate and each qubit's marginal bias
- [ ] `--dry-run` shows the lowered circuit and cost
