---
id: 33
uid: 8ad3bf24-f6b6-4202-98c2-70831281c829
title: Print a receipt with every flip
type: feature
status: backlog
milestone: v0.3
depends_on:
- 32
created: 2026-11-01
updated: 2026-11-02
priority: p1
effort: s
area: cli
---

## Problem

The over-engineered coin earns its keep through provenance: every bit should say where it
came from.

## Proposal

`coin flip` prints the outcome, then backend, qubit, job ID, date, extractor and batch.
`--json` emits the same as one object.

## Acceptance criteria

- [ ] The receipt's job ID resolves to an archived run in `data/runs/`
- [ ] `--json` output validates against a documented schema
- [ ] `--quiet` prints only HEADS or TAILS

## 2026-11-02

From 0032: a harvest run's shots plus its batch's seed determine every bit, so a receipt that points at an archived run makes the flip checkable, and an archived run whose batch is not yet spent makes those flips predictable. Receipts should resolve to runs committed after their batch is spent; the pool's provenance has run, job_id, qubit, seed and seed_bits.
