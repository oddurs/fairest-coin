---
id: 50
uid: 9b668e87-3d16-4653-bf9b-8b212016e1c7
title: Prove a fresh clone regenerates everything
type: chore
status: backlog
milestone: v1.0
depends_on:
- 25
- 34
- 45
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: tooling
---

## Problem

The v1.0 promise is that every figure and number is reproducible from the archive.

## Proposal

A CI job that clones fresh, syncs, regenerates every figure and every table in the
chapters, and fails on any difference.

## Acceptance criteria

- [ ] CI fails when a committed figure is edited by hand (demonstrated once in a PR)
- [ ] Every number in the chapters is either generated or links to the run that produced it
