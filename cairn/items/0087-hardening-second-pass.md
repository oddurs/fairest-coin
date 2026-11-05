---
id: 87
uid: daa7ca9c-5a43-42c2-8ce1-79eed1bcbb3f
key: v0.3.2
title: Hardening, second pass
type: milestone
status: done
created: 2026-11-04
updated: 2026-11-05
closed_at: 2026-11-05
priority: p1
due: 2026-11-11
---

## Ships

v0.3.2: every defect found by the review of v0.3 as released is fixed: a committed run can
never be pooled, the archive survives a power cut, recovery trusts only its own records,
the min-entropy estimate claims no more than it can see, and the suite pins what it tests.

## Done when

- [x] No path pools a run whose shots are public
- [x] Every archive write is as durable as a pool write
- [x] `coin recover` acts only on records this user wrote for this archive, and survives a malformed one
- [x] Code, CLI and essay state what the min-entropy estimate cannot detect
- [x] Every surviving non-equivalent mutant from the review is killed
- [x] Tagged `v0.3.2`

## 2026-11-05

Shipped as v0.3.2 on 30c2ce6. (1) 0088: relative, absolute and symlinked paths to a committed run are refused, and so is a repository git cannot read (tests; the installed tool refused both). (2) 0089: every archive, pending-record and pool write goes through coin.durable (spy tests, 12 mutants killed). (3) 0090: private fallback, other users' and contradictory records refused, malformed records listed (tests, 11 mutants killed). (4) 0091: extract.py, chapter 3, the changelog and the CLI say what the estimate misses and that ε is conditional (parity test pins the miss). (5) 33 non-equivalent survivors: durability in 0089, recovery in 0090, constants and seeds in 0091, the other 20 in 0092, each replayed from the reviewer's definition. (6) Tagged v0.3.2.

## Result

v0.3.2 released: every defect from the review of v0.3 as released is fixed with its test, and every non-equivalent surviving mutant is killed.
