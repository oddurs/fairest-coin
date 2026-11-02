---
id: 78
uid: da654dc1-1702-46f4-babd-6ae50f110c23
title: Pool each job once, only harvest runs, and publish the extraction record
type: bug
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
depends_on:
- 77
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
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

- [x] A job already pooled is refused whatever its directory is called (test)
- [x] `--from-run` refuses runs whose prediction is not a harvest's, and runs that already carry an extraction record (tests)
- [x] `coin publish RUN` writes extraction.json into a harvest run only once its batch is spent, and refuses otherwise (tests)

## 2026-11-02

Pool dedupe keys on job_id (falling back to the run name without one); --from-run refuses runs that are not harvests, that carry extraction.json, or that git tracks; coin publish writes extraction.json atomically through archive.add_record only when every bit of the job's single batch is spent and the directory is the one pooled. Limitation, documented: a copy of public shots made outside git cannot be recognised. Review fixes: multiple batches per job, atomic record, README's commit-after-spent rule restored, run-name fallback, copy refused, no-prediction message, notes printed.

## Result

One batch per job; only unpublished, untracked harvest runs can be pooled; coin publish writes a spent harvest's extraction record (archive.add_record, atomic, once).
