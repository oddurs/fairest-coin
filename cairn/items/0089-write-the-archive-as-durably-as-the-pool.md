---
id: 89
uid: a8b1a6c8-0d5f-46f7-94ec-3dd99cf4ce8d
title: Write the archive as durably as the pool
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

Found by the review of v0.3 on 2026-11-04. The pool writes with F_FULLFSYNC and syncs the directory. `archive.write_run`
syncs nothing before its rename, `hardware._write_json_atomic` uses plain `fsync` (which on
macOS does not flush the drive cache) and never syncs the directory, and
`archive.add_record` does neither. After a power cut a harvest's batch can survive while
its archived run and its pending record do not: the prediction is gone and `coin recover`
has nothing to recover from. The suite does not notice if any sync in the pool is removed.

## Acceptance criteria

- [x] One durable-write helper serves the pool, the archive, the pending record and add_record
- [x] Each write syncs the file with F_FULLFSYNC where available, and its directory, before it is relied on (test that spies on the syncs)
- [x] The pending record is unlinked only after the archived run is durable (test)

## 2026-11-04

New coin.durable: sync (F_FULLFSYNC, else fsync), sync_directory, make_directory (each created level's parent synced), write (synced file, caller syncs the directory) and replace (synced temp, rename, directory synced). The pool, write_run (every file, the staging dir, then the runs dir after the rename), add_record, the pending record and the runs dir all use it. Tests spy on syncs by inode, in order. Replayed 12 mutants (fsync to pass, F_FULLFSYNC skipped, fallback inverted, each dropped sync, each plain write or mkdir): all killed.

## Result

Every write the project relies on goes through coin.durable: files synced with F_FULLFSYNC where available, names made durable by syncing their directory, and the pending record removed only after the archived run is durable. Tested by spying on syncs; 12 mutants killed.
