---
id: 90
uid: add44f68-5422-4823-9fa5-0e6ad3dbf76e
title: Trust only this user's pending records in recovery
type: bug
status: backlog
milestone: v0.3.2
created: 2026-11-04
updated: 2026-11-04
priority: p1
effort: m
area: hardware
---

## Problem

Found by the review of v0.3 on 2026-11-04. `pending_runs` adopts any `.pending-*.json` in the shared temp dir whose `runs_dir`
matches, and `recover` prefers one that already holds a result: on Linux another user can
plant fake shots and a fake prediction, archived under whatever job id the record claims,
while the real record is deleted. A record holding `[]` crashes `coin recover` for
everyone. `_keep_result` writes a harvest's still-secret shots to the temp dir with mode
0644. `_archived` matches `*-<job_id>`, so job `abc` finds the run of job `x-abc`.

## Acceptance criteria

- [ ] Records outside the runs directory live in a per-user directory created 0700, are written 0600, and records owned by another user are ignored (test)
- [ ] A record whose result names a different job than the one recovered is refused (test)
- [ ] A malformed record is listed as a problem and never stops recovery of the others (test)
- [ ] `_archived` matches a run's job id exactly (test)
- [ ] The temp-dir fallback and the runs_dir ownership filter are each exercised by a test
