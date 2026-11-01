---
id: 43
uid: 0caec3cd-6cab-4257-b430-9f7fbaa1e077
title: Choose Bell settings with the coin's own bits
type: feature
status: backlog
milestone: v0.4
depends_on:
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

If a PRNG picks the settings, the certificate is circular. Using the v0.3 pool closes the
loop: the coin certifies the next round of coin flips.

## Proposal

Draw the per-shot settings for a CHSH batch from the entropy pool, run it, and credit the
batch's outcome bits to the pool as certified, recording seed bits spent against bits
produced. The accounting is the randomness-expansion story of Pironio et al. (2010) at
classroom scale.

## Acceptance criteria

- [ ] Setting bits come only from the pool, and the run records which batch supplied them
- [ ] The run reports seed bits consumed and output bits produced
- [ ] A batch whose S does not exceed 2 at 5σ credits nothing to the pool
