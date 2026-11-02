---
id: 3
uid: caf9d948-3f61-4d0d-a8ec-3b4f6c0ed806
key: v0.3
title: The fair coin
type: milestone
status: done
created: 2026-11-01
updated: 2026-11-02
closed_at: 2026-11-02
priority: p2
due: 2026-12-06
---

## Ships

`coin harvest` collects real hardware bits, debiases them, and fills a local pool;
`coin flip` spends one bit from that pool with a receipt. Chapter 3 shows the coin made
fair, and why no statistical test can prove it.

## Done when

- [x] Extracted bits pass the test battery; raw bits fail it where the bias says they should
- [x] The independence assumption behind the extractor is tested on archived data, not assumed
- [x] A pool bit is never handed out twice
- [x] Every flip prints where its bit came from
- [x] Tagged `v0.3.0`

## Explicitly not in this milestone

- Certification: v0.3 ends on the question "if tests can't prove it, what can?"

## 2026-11-02

Evidence: (1) extracted bits pass the battery while raw shots fail it — docs/figures/extraction.svg (qubits 88, 34) and chapter 3's harvest (qubit 104: raw monobit p = 2.1e-13; Toeplitz output, smallest p 0.21); (2) independence tested on archived data in spike 0028 (analysis/independence.py, tests/test_independence.py); (3) never twice: tests/test_pool.py concurrency and crash tests, plus an adversarial review racing 12–16 processes with SIGKILLs (0 duplicates); (4) every pool flip prints a receipt (tests/test_receipt.py, docs/receipt.schema.json); (5) tag v0.3.0.

## Result

Shipped as v0.3.0: coin harvest fills a local pool with Toeplitz-extracted hardware bits (half the min-entropy estimate spent), coin flip spends one with a receipt, never twice. Chapter 3 makes the coin fair and ends on π passing every test: no test can prove randomness.
