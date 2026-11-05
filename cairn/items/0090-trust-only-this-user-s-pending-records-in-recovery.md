---
id: 90
uid: add44f68-5422-4823-9fa5-0e6ad3dbf76e
title: Trust only this user's pending records in recovery
type: bug
status: done
milestone: v0.3.2
assignee: Oddur Sigurdsson
created: 2026-11-04
updated: 2026-11-04
closed_at: 2026-11-04
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

- [x] Records outside the runs directory live in a per-user directory created 0700, are written 0600, and records owned by another user are ignored (test)
- [x] A record whose result names a different job than the one recovered is refused (test)
- [x] A malformed record is listed as a problem and never stops recovery of the others (test)
- [x] `_archived` matches a run's job id exactly (test)
- [x] The temp-dir fallback and the runs_dir ownership filter are each exercised by a test

## 2026-11-04

Fallback moved from the shared temp dir to $XDG_STATE_HOME/fairest-coin/pending (default ~/.local/state), created 0700 and refused unless this user owns it and no one else can use it; it also survives a reboot, which /tmp does not. Records are written 0600. pending_runs lists as problems, never adopts: records another user owns, non-objects, a job id that is not one, a result for another job. _archived matches <date>-<job id> exactly. Found while testing: the lock's unlink in _waiting's finally raised PermissionError in a read-only runs dir and hid the message saying where the result was kept; it is now suppressed (a stale lock is cleared by _still_waiting). Also found: tests calling monkeypatch.undo() reverted conftest's COIN_POOL, so a later default Pool would have pointed at the user's pool; conftest now uses its own patcher (the real pool is untouched: its files date from the 2026-11-02 harvest). 11 mutants replayed, all killed.

## Result

Recovery trusts only this user's own, self-consistent records: the fallback is a private state directory (0700, records 0600), other users' and contradictory records are listed as problems and never archived, a malformed record no longer stops the others, and archived runs match by exact name; 11 mutants killed.
