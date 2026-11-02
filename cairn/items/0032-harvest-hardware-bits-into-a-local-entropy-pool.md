---
id: 32
uid: 97ca228f-e91b-4ea3-8773-c4f787f96dbe
title: Harvest hardware bits into a local entropy pool
type: feature
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 22
- 28
- 30
- 70
created: 2026-11-01
updated: 2026-11-02
closed_at: 2026-11-02
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

- [x] A spent bit is never returned again, including across processes (file locking, tested)
- [x] An empty pool exits non-zero and says to run `coin harvest`
- [x] `coin pool` shows remaining bits per batch
- [x] Raw harvested bits are archived like any other run

## 2026-11-01

From spike 0028: extract with Toeplitz hashing (0070), not von Neumann. And screen each batch's qubit with analysis/independence.py's tests: 5 of 156 qubits had time structure in the chip-map run, and which ones will change between runs.

## 2026-11-01

From 0070: use toeplitz_extract's default (half the min-entropy estimate) and record the Extraction fields per batch: entropy_per_bit, estimate, epsilon, input_bits, seed_used, and the seed itself. Qubit 88's 100,000 chip-map shots give about 44,000 bits this way.

## 2026-11-01

Decision: no separate independence screen. The earlier note asked for one because von Neumann needs independence; the pool now extracts with Toeplitz hashing (0070), whose guarantee rests on the min-entropy estimate, and that estimate's guessers (lag, online Markov, phase, worst block) look for the structure the screen did. Each batch records the estimate and the half of it spent.

## 2026-11-02

Evidence. (1) tests/test_pool.py: six processes drain 300 bits one at a time with no (batch, offset) repeated; removing the lock fails it 3/3. Independent adversarial review: 12–16 workers mixing take/add, 13,896 bits handed out, 0 duplicates; random SIGKILLs, 0 duplicates, some bits lost (by design). Crash mid-add and mid-write tests catch the write-order and non-atomic-write mutants. (2) Empty pool: coin flip exits 1 with 'run `coin harvest`'. (3) coin pool prints bits, spent and remaining per batch. (4) harvest submits through hardware.submit, so the raw run is archived with prediction, calibration and memory; tested with a fake transport, and the batch re-derives from the archived shots plus the recorded seed. Review fixes: harvest refuses before submitting if it would yield no bits or the pool is unwritable; --from-run re-extracts an archived run; the same run is refused twice; F_FULLFSYNC on macOS and directory fsync; microsecond batch names; truncated batches spend nothing. Design limit, documented: archived shots plus seed determine the batch, so a harvest run should be committed only once its batch is spent.

## Result

coin.pool (Pool.add/take/status, flock + atomic durable writes) and coin.harvest (pick_qubit, plan, harvest, extract_run). CLI: coin harvest --backend --shots (--dry-run|--submit|--from-run DIR), coin pool, and coin flip without --sim spends pool bits. Commit a harvest run only after its batch is spent.
