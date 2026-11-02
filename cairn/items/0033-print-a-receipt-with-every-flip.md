---
id: 33
uid: 8ad3bf24-f6b6-4202-98c2-70831281c829
title: Print a receipt with every flip
type: feature
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 32
created: 2026-11-01
updated: 2026-11-02
closed_at: 2026-11-02
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

- [x] The receipt's job ID resolves to an archived run in `data/runs/`
- [x] `--json` output validates against a documented schema
- [x] `--quiet` prints only HEADS or TAILS

## 2026-11-02

From 0032: a harvest run's shots plus its batch's seed determine every bit, so a receipt that points at an archived run makes the flip checkable, and an archived run whose batch is not yet spent makes those flips predictable. Receipts should resolve to runs committed after their batch is spent; the pool's provenance has run, job_id, qubit, seed and seed_bits.

## 2026-11-02

Evidence, tests/test_receipt.py: (1) after a harvest, the --json receipt's run loads from the archive with the same job id, qubit and backend; (2) --json output validates against docs/receipt.schema.json (a small validator in the test covers the schema features used, and is itself shown to catch an extra and a missing field); (3) --quiet prints exactly HEADS or TAILS. --json and --quiet refuse --shots (a receipt is one flip) and --json refuses --sim (no receipt).

## Result

coin flip (pool) prints the face then a receipt: backend, qubit, job, harvest date, run, bit position in its batch, extraction entropy and ε. --json emits it per docs/receipt.schema.json; --quiet prints only the face. pool.receipt(draw, flipped_at) builds it.
