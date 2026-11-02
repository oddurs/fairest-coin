---
id: 32
uid: 97ca228f-e91b-4ea3-8773-c4f787f96dbe
title: Harvest hardware bits into a local entropy pool
type: feature
status: backlog
milestone: v0.3
depends_on:
- 22
- 28
- 30
- 70
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: extract
qpu: 'true'
---

## Problem

One job per flip would exhaust the monthly allowance in an afternoon. Bits should be
harvested in batches and spent one at a time.

## Proposal

`coin harvest --backend NAME --shots N` runs the coin on the best-calibrated qubit,
debiases it with the extractor chosen by the independence spike, and appends the bits to a
pool in the user data directory, recording provenance per batch. `coin flip` takes the next
unspent bit.

## Acceptance criteria

- [ ] A spent bit is never returned again, including across processes (file locking, tested)
- [ ] An empty pool exits non-zero and says to run `coin harvest`
- [ ] `coin pool` shows remaining bits per batch
- [ ] Raw harvested bits are archived like any other run

## 2026-11-01

From spike 0028: extract with Toeplitz hashing (0070), not von Neumann. And screen each batch's qubit with analysis/independence.py's tests: 5 of 156 qubits had time structure in the chip-map run, and which ones will change between runs.

## 2026-11-01

From 0070: use toeplitz_extract's default (half the min-entropy estimate) and record the Extraction fields per batch: entropy_per_bit, estimate, epsilon, input_bits, seed_used, and the seed itself. Qubit 88's 100,000 chip-map shots give about 44,000 bits this way.
