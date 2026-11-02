---
id: 30
uid: 7506723c-f012-4600-b246-a95ab65f466c
title: Debias bits with the von Neumann extractor
type: feature
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: s
area: extract
---

## Problem

A biased coin can be made perfectly fair: flip twice, keep 01 as 0 and 10 as 1, discard
00 and 11. It costs throughput, at p(1−p) output bits per input bit.

## Proposal

`coin/extract.py`: `von_neumann(bits) -> bits`, plus the iterated Peres variant that
recovers some of the discarded entropy. Both are pure functions over numpy bit arrays.

## Acceptance criteria

- [x] Property test: on i.i.d. input of any bias, output is unbiased within 4σ over 10⁶ bits
- [x] Output yield matches p(1−p) within sampling error
- [x] Peres yields strictly more bits than single-pass von Neumann on the same input

## 2026-11-01

From spike 0028: von Neumann's output was fair on all 156 chip-map qubits, but on qubit 88 its output bits are correlated (+9.8σ at lag 1), from a periodic disturbance in the input. Teach it as the extractor that needs independence, and apply it only to qubits that pass the independence screen.

## 2026-11-01

Evidence: tests/test_extract.py. (1) Hypothesis over bias 0.05–0.95, 10⁶ bits each: von Neumann and Peres outputs within 4σ of fair; Peres's output lag-1 within 4σ. (2) Yield within 4σ of the binomial count for 2p(1−p) per pair. (3) Peres strictly longer on every drawn input. Measured rates on 10⁶ bits: p=0.5 VN 0.250, Peres 0.957 (h 1.0); p=0.7 VN 0.210, Peres 0.839 (h 0.881); p=0.9 VN 0.090, Peres 0.440 (h 0.469). Mutants (no pair filter; raw u in output; v from all pairs) each fail 2–6 tests. analysis/independence.py now calls coin.extract.von_neumann; its spike-0028 output is unchanged.

## Result

coin.extract: von_neumann (01→0, 10→1) and peres (depth 10 by default, 93–96% of the entropy). Pure numpy; i.i.d. is assumed, never checked. analysis/independence.py uses the library extractor.
