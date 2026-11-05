---
id: 44
uid: 05c72334-9bfd-4833-864a-73495c492ddd
title: Attach the batch's S value to every receipt
type: feature
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 33
- 43
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
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

- [x] Certified and uncertified bits are distinguishable in both text and `--json` output
- [x] `coin flip --certified` draws only certified bits, or exits non-zero if none remain

## 2026-11-05

Claimed past its block on 0043 (2026-11-05): 0043's code (coin.certify, certified batches) is merged and its tests make certified batches, so receipts can be built and tested now; only 0043's hardware run waits on the owner.

## 2026-11-05

Pool.take(n, certified=...) keeps certified and plain batches apart, so a plain flip (or a CHSH run's settings) never spends a certified bit, and coin flip --certified draws only certified ones, exiting 1 with 'run coin certify' when none remain. Receipts gain certified (boolean, always) and, on a certified bit, certificate: the pair, S, S_low, its ε, the certified rate per round, and the batches that chose the settings; qubit is null there. Text output marks a plain bit 'not Bell-certified' and a certified one with its S, S_low, ε, qubits, rate and settings batches. docs/receipt.schema.json documents both; the test validator learned type lists, null, boolean and arrays. Four mutants replayed, all killed.

## Result

Receipts say whether a bit is Bell-certified and, if so, carry S, S_low with its ε, the certified rate per round, the pair and the settings' batches, in text and --json (schema documented); coin flip --certified spends only certified bits and exits non-zero when none remain; plain and certified bits are never mixed.
