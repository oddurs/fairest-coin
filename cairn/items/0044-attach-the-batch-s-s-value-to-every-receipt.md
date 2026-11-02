---
id: 44
uid: 05c72334-9bfd-4833-864a-73495c492ddd
title: Attach the batch's S value to every receipt
type: feature
status: backlog
milestone: v0.4
depends_on:
- 33
- 43
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: cli
---

## Problem

The over-the-top payoff is a coin flip that carries a Bell-violation certificate.

## Proposal

Receipts for bits from certified batches add S, S_low with its ε, the certified min-entropy
per round, and the batch that supplied the settings.

## Acceptance criteria

- [ ] Certified and uncertified bits are distinguishable in both text and `--json` output
- [ ] `coin flip --certified` draws only certified bits, or exits non-zero if none remain
