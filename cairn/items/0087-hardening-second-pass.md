---
id: 87
uid: daa7ca9c-5a43-42c2-8ce1-79eed1bcbb3f
key: v0.3.2
title: Hardening, second pass
type: milestone
status: backlog
created: 2026-11-04
updated: 2026-11-04
priority: p1
due: 2026-11-11
---

## Ships

v0.3.2: every defect found by the review of v0.3 as released is fixed: a committed run can
never be pooled, the archive survives a power cut, recovery trusts only its own records,
the min-entropy estimate claims no more than it can see, and the suite pins what it tests.

## Done when

- [ ] No path pools a run whose shots are public
- [ ] Every archive write is as durable as a pool write
- [ ] `coin recover` acts only on records this user wrote for this archive, and survives a malformed one
- [ ] Code, CLI and essay state what the min-entropy estimate cannot detect
- [ ] Every surviving non-equivalent mutant from the review is killed
- [ ] Tagged `v0.3.2`
