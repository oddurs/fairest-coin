---
id: 24
uid: 2450d34a-04b8-4902-b7d9-906f577cf23c
title: Regenerate figures deterministically from the archive
type: feature
status: backlog
milestone: v0.2
depends_on:
- 19
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: figures
---

## Problem

A figure that cannot be regenerated is a claim, not evidence. Figures must come from the
archive and nothing else.

## Proposal

`scripts/figures` renders every figure under `docs/figures/` from `data/runs/` with
matplotlib (optional `figures` dependency group), as SVG with fixed metadata so the output
is byte-stable. `scripts/task` gains nothing; CI runs it as part of `build`.

## Acceptance criteria

- [ ] Running it twice produces byte-identical files
- [ ] CI fails if the committed figures differ from the regenerated ones
- [ ] Figures render legibly on both light and dark GitHub themes
