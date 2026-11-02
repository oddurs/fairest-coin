---
id: 43
uid: 0caec3cd-6cab-4257-b430-9f7fbaa1e077
title: Choose Bell settings with the coin's own bits
type: feature
status: backlog
milestone: v0.4
depends_on:
- 41
- 32
- 42
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: chsh
qpu: 'true'
---

## Problem

If a PRNG picks the settings, the certificate is circular. Using bits from the v0.3 pool
closes the loop: the coin's own bits choose how the next coins are measured.

What the loop cannot do with uniform settings is produce more randomness than it consumes.
Each round spends two setting bits, and the min-entropy a round certifies is at most
1 − log₂(1 + √(2 − S²/4)) (Pironio et al., 2010): 0.27 bits at S = 2.5, 0.49 at S = 2.7.
And the per-round bound assumes the rounds behave alike, which spikes 0028 and 0069 found
the chip does not always do.

## Proposal

Draw the per-shot settings for a CHSH batch from the entropy pool. The pool was spent by
chapter 3, so this needs a fresh harvest first (QPU time, with the owner's approval). Run
the batch, then extract its outcome bits with Toeplitz hashing at the certified rate
(`toeplitz_extract(..., entropy_per_bit=h)` with h from S_low), and credit them to the pool
as certified. Record setting bits in, certified bits out, and the net, and say plainly that
it is negative and why.

## Acceptance criteria

- [ ] Setting bits come only from the pool, and the run records which batch supplied them
- [ ] Certified bits are Toeplitz-extracted at the min-entropy S_low certifies, never credited raw
- [ ] The run reports setting bits consumed, certified bits produced and the net, and claims no expansion
- [ ] A batch whose S_low does not exceed 2 credits nothing to the pool
