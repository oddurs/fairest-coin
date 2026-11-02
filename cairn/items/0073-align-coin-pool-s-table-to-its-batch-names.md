---
id: 73
uid: 7e5b6ace-516e-44a8-b112-3df072ff16f5
title: Align coin pool's table to its batch names
type: bug
status: done
milestone: v0.3
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p3
effort: s
area: cli
---

## What happens

## What should happen

## Reproduction

1.
## Problem

`coin pool` printed its table with a 34-character batch column, but batch names (UTC time
to the microsecond plus the job id) run to 42 characters. So the numbers no longer lined up
under their headings: seen when the chapter 3 batch was spent.

## Acceptance criteria

- [x] Every line of `coin pool`'s table has the same width, for real batch names (test fails before the fix)

## Result

coin pool sizes its batch column to the longest name; a test with a real-length name fails before the fix.
