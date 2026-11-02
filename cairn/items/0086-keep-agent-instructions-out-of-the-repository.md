---
id: 86
uid: 7150e2ba-685f-45ff-b5ac-6307c0ed5579
title: Keep agent instructions out of the repository
type: chore
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p2
effort: s
area: tooling
---

## Problem

The repository tracks an instruction file and a rules directory whose names belong to one
coding tool. The project's rule is that no tool is named in anything that reaches git;
those two paths are the last exception. Their content is not tool-specific: it is the
workflow every contributor follows and the physics conventions the code obeys.

## Approach

- The instructions become `AGENTS.md`; the physics conventions become
  `docs/conventions.md`, where a human reader finds them too.
- Each tool's own files stay local to the clone, listed in `.git/info/exclude`, so the
  tracked tree names none of them.
- `scripts/agent start` links every literal path in `.git/info/exclude` that exists in
  the primary checkout into the new worktree, so local files reach every worktree
  without the script naming any of them.

Not in scope: rewriting history. Earlier commits keep the old files; removing them would
re-point every merged PR and break the release tags.

## Acceptance criteria

- [x] No tracked path or file outside the attribution guard and its tests names a coding tool
- [x] `scripts/agent start` links the primary checkout's excluded local files into the new worktree, and skips globs and paths the worktree already has (test)
- [x] AGENTS.md, CONTRIBUTING.md and docs/conventions.md say where the instructions and conventions now live

## 2026-11-02

git ls-files names no tool; git grep finds tool names only in scripts/attribution and tests/test_hooks.py, the guard and its tests. tests/test_agent.py covers linking (literal file, directory, glob, negation, absent path, tracked file, clean status, worktree remove keeps the primary checkout's files) and git's default and a missing exclude file. A mutant that skips the link call fails it. The glob filter I first wrote was redundant — -e never matches a quoted pattern — so it was removed, not tested.

## Result

The instructions are AGENTS.md and the physics conventions docs/conventions.md; tool files are local, listed in .git/info/exclude, and scripts/agent start links them into each worktree (tested). Only the attribution guard and its tests name a tool. History is unchanged.
