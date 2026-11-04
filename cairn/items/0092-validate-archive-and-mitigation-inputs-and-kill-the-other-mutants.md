---
id: 92
uid: fa2abc20-4cdc-4d50-9618-17fe805ffee2
title: Validate archive and mitigation inputs and kill the other mutants
type: chore
status: backlog
milestone: v0.3.2
created: 2026-11-04
updated: 2026-11-04
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

- [ ] The archive and mitigation refuse the invalid inputs listed (tests)
- [ ] Each listed mutant is killed by a test, replayed and recorded in a note
