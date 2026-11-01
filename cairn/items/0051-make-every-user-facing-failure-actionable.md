---
id: 51
uid: c9a94b47-0943-4541-89a3-bd026a5455b3
title: Make every user-facing failure actionable
type: chore
status: backlog
milestone: v1.0
depends_on:
- 44
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: cli
---

## Problem

Before v1.0 the tool has grown five commands and a network dependency. Each failure a user
can hit should exit non-zero and say what to do.

## Proposal

Audit `coin` for missing token, no network, job failure or timeout, empty pool, corrupt
archive and unknown backend. Give each one an exit code and a message, documented in
`coin --help`.

## Acceptance criteria

- [ ] Each failure listed has a test asserting its exit code and message
- [ ] No traceback reaches the user for any of them
