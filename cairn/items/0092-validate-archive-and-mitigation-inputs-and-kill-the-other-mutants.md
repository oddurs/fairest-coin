---
id: 92
uid: fa2abc20-4cdc-4d50-9618-17fe805ffee2
title: Validate archive and mitigation inputs and kill the other mutants
type: chore
status: done
milestone: v0.3.2
assignee: Oddur Sigurdsson
created: 2026-11-04
updated: 2026-11-04
closed_at: 2026-11-04
priority: p2
effort: m
area: tooling
---

## Problem

Found by the review of v0.3 on 2026-11-04. 72 of 105 non-equivalent mutants were caught. Besides those filed separately, these
survive: `ibm` not marking `maybe_submitted` when `job_id()` fails; HEADS/TAILS swapped in
receipts; `serial` wrapping with zeros; the harvest forecast taking the best of its
samples, or one sample; the 1,000-bit boundary; `shots_of` accepting several qubits;
`recover` not preferring a record with a result; the race-loss path swallowing
BaseException; the usage-key preference; angles rounded in the circuit check; the pool's
batch-name filter and duplicate-name check; the archive's counts-sum check. The archive
accepts negative counts, a prediction together with a no-prediction reason, and non-integer
qubits; mitigation accepts negative frequencies and unknown error keys.

## Acceptance criteria

- [x] The archive and mitigation refuse the invalid inputs listed (tests)
- [x] Each listed mutant is killed by a test, replayed and recorded in a note

## 2026-11-04

The archive and mitigation already refused every input listed; nothing tested it, so each check could be deleted unnoticed. Tests added, and each of the reviewer's exact mutants replayed from its own definitions against this branch: P8 (duplicate batch name), P9 (non-batch .bits file), P14 (receipt face), H2 and H13 (forecast is the worst of five: 5,000 shots at 0.6 give 1,394/1,378/1,485/1,518/1,410), H11 (shots_of on two qubits), H12 (999 refused, 1,000 accepted), A2 (counts sum without memory), A6 (negative count summing right), A14 (prediction and reason), A16 (non-integer qubits), M2 (negative frequency, all ≤1, summing to 1), M6 (an extra error key), B8 (every rotation of NIST's serial example), I6 (an rz nudged by 1e-3), I7 (maybe_submitted when job_id fails), I11 (the charge wins over quantum_seconds), E7 (a biased tail only the last block sees), W8 (a record with the result beats a newer one without), W12 (Ctrl-C after a racing archive still stops): 20 of 20 killed. The reviewer's equivalent mutants (E9/E10, E16, E19, E20, E22, B6, B7, B9, I3, I10, W11, W23, A15) are left as equivalent; the durability, constant and seed survivors were killed in 0089, 0090 and 0091.

## Result

Every surviving non-equivalent mutant from the v0.3 review is killed: 20 here (pool, harvest, archive, mitigation, battery, IBM adapter, extract, recovery), the rest in 0089–0091; each replayed from the reviewer's own definition.
