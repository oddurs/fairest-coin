---
id: 88
uid: c7c4cb75-7510-4353-86c5-c6d5833f2ab5
title: Refuse a committed run however its path is written
type: bug
status: backlog
milestone: v0.3.2
created: 2026-11-04
updated: 2026-11-04
priority: p0
effort: s
area: extract
---

## Problem

Found by the review of v0.3 on 2026-11-04. `_tracked_by_git` passes the path to `git ls-files` while also running git inside
that path, so a relative path is resolved twice and matches nothing. `coin harvest
--from-run data/runs/<run>` — the natural way to type it — pools a committed run whose
shots are public, and its bits are predictable. Any git failure (exit 128, for example a
`safe.directory` refusal) also reads as "not tracked". The test passes an absolute path.

## Acceptance criteria

- [ ] A committed run is refused given a relative path, an absolute path, or a path through a symlink (test)
- [ ] A git failure inside a work tree refuses the run and says why, rather than passing it (test)
