---
id: 13
uid: 334ce51e-8e6f-4518-84b2-ca80aeb66e43
title: Make the README the spine of the essay
type: docs
status: done
milestone: v0.1
assignee: Oddur Sigurdsson
depends_on:
- 10
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] The quickstart commands run on a fresh clone exactly as written
- [x] Chapters that do not exist yet are listed as upcoming, not linked
- [x] Describes only what the code does today

## 2026-11-01

Verified on a fresh install: 'uv tool install git+https://github.com/oddurs/fairest-coin' into an isolated UV_TOOL_DIR printed the README's quickstart output byte for byte; a fresh clone ran scripts/setup and scripts/agent doctor clean. README.md is now checked by tests/test_chapters.py like a chapter.

## Result

README.md: thesis, a quickstart (install, coin flip --sim, pinned 10,000-shot output checked by tests/test_chapters.py), chapter index (0 and 1 linked, later ones 'upcoming in vX'), Development, License. The README is held to the chapter drift guard.
