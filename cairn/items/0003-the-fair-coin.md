---
id: 3
uid: caf9d948-3f61-4d0d-a8ec-3b4f6c0ed806
key: v0.3
title: The fair coin
type: milestone
status: backlog
created: 2026-11-01
updated: 2026-11-01
priority: p2
due: 2026-12-06
---

## Ships

`coin harvest` collects real hardware bits, debiases them, and fills a local pool;
`coin flip` spends one bit from that pool with a receipt. Chapter 3 shows the coin made
fair, and why no statistical test can prove it.

## Done when

- [ ] Extracted bits pass the test battery; raw bits fail it where the bias says they should
- [ ] The independence assumption behind the extractor is tested on archived data, not assumed
- [ ] A pool bit is never handed out twice
- [ ] Every flip prints where its bit came from
- [ ] Tagged `v0.3.0`

## Explicitly not in this milestone

- Certification: v0.3 ends on the question "if tests can't prove it, what can?"
