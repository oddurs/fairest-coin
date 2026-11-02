---
id: 78
uid: da654dc1-1702-46f4-babd-6ae50f110c23
title: Pool each job once, only harvest runs, and publish the extraction record
type: bug
status: backlog
milestone: v0.3.1
depends_on:
- 77
created: 2026-11-02
updated: 2026-11-02
priority: p1
effort: m
area: extract
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. The pool refuses a run already pooled by comparing directory names, so a copied
run directory pools the same shots twice. `--from-run` accepts any run, including the
published chapter 3 harvest, whose bits then come from a fresh seed while the receipt
credits the qubit. A receipt can only be checked with the local pool's seed record, and
chapter 3's `extraction.json` was written by hand.

## Acceptance criteria

- [ ] A job already pooled is refused whatever its directory is called (test)
- [ ] `--from-run` refuses runs whose prediction is not a harvest's, and runs that already carry an extraction record (tests)
- [ ] `coin publish RUN` writes extraction.json into a harvest run only once its batch is spent, and refuses otherwise (tests)
