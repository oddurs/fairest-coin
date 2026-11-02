---
id: 70
uid: db019e14-aa34-4a16-a646-95b0910bbff8
title: Extract with Toeplitz hashing from a min-entropy estimate
type: feature
status: backlog
milestone: v0.3
depends_on:
- 28
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: extract
---

## Problem

Spike 0028 found that 5 of the chip map's 156 qubits are not independent from shot to shot:
- a telegraph switcher;
- two periodic lines;
- short memory;
- slow wander.

On one of them (qubit 88), von Neumann's output passes every fairness test, yet its bits
are correlated with each other at +9.8σ. An entropy pool that assumes i.i.d. bits would
hand that out as fair. It needs an extractor whose guarantee rests on min-entropy alone,
not on independence.

## Proposal

`coin/extract.py`:
- `min_entropy(bits) -> float`, per bit: a conservative estimate. Take the lower of the
  most-common-value and Markov estimates, after NIST SP 800-90B §6.3.1 and §6.3.3.
- `toeplitz(bits, seed, m) -> bits`: multiply the input by the m × n Toeplitz matrix
  defined by `seed` (n + m − 1 bits), over GF(2). The output length comes from the
  leftover hash lemma, m = ⌊n·h − 2·log₂(1/ε)⌋, with ε chosen and recorded.

The seed comes from the operating system (`secrets`) and is stored with each batch. A
Toeplitz extractor is strong, so the seed may be public.

## Acceptance criteria

- [ ] `toeplitz` matches an explicit matrix-vector product over GF(2) for random small sizes (property test)
- [ ] On synthetic sources whose min-entropy is known (biased i.i.d., and a Markov chain), `min_entropy` never exceeds the true value
- [ ] Output length follows the leftover hash lemma for a stated ε, and the code refuses to output more
- [ ] On qubit 88's shots from data/runs/2026-11-02-dbjuh5d6p51s73cljo60, the Toeplitz output passes the 0031 battery's serial test where von Neumann's output fails it
