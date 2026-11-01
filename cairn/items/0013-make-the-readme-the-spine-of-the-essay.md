---
id: 13
uid: 334ce51e-8e6f-4518-84b2-ca80aeb66e43
title: Make the README the spine of the essay
type: docs
status: backlog
milestone: v0.1
depends_on:
- 10
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: essay
---

## Problem

The README is the first thing anyone reads. It should state the question, show what works
today, and route the reader into the chapters.

## Proposal

Rewrite `README.md`: the thesis in one paragraph, a quickstart that installs and flips the
simulated coin, the chapter index with each chapter's status, and a Development section
pointing at `scripts/agent` and `CONTRIBUTING.md`.

## Acceptance criteria

- [ ] The quickstart commands run on a fresh clone exactly as written
- [ ] Chapters that do not exist yet are listed as upcoming, not linked
- [ ] Describes only what the code does today
