---
id: 43
uid: 0caec3cd-6cab-4257-b430-9f7fbaa1e077
title: Choose Bell settings with the coin's own bits
type: feature
status: doing
milestone: v0.4
assignee: Oddur Sigurdsson
claimed: 2026-11-05
depends_on:
- 41
- 32
- 42
created: 2026-11-01
updated: 2026-11-06
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

## 2026-11-05

Code first, in its own PR. coin.certify: settings_from_pool (two pool bits a round, choice 2a + b; records batch, offset and count; the bits are spent), certified_rate (Pironio et al. 2010: 1 − log₂(1 + √(2 − S²/4)), 0 at S ≤ 2, 1 at 2√2; 0.268 at 2.5, 0.493 at 2.7), certify (refuses a run whose settings did not come from the pool, one already published, and in the CLI one git tracks; S_low ≤ 2 credits nothing; else the run's two outcome bits a round are Toeplitz-hashed at rate/2 per bit, ⌊n·rate⌋ − 64 bits out, pooled as a certified batch with S, S_low, ε, the rate and the settings' source), and report (setting bits in, certified bits out, net, and that it does not expand randomness). coin run chsh --predict now draws settings from the pool after validating the plan with throwaway settings, so a plan that cannot run spends nothing; --dry-run never spends. coin certify RUN. A certified run, like a harvest, is committed only once its batch is spent (coin publish works for it unchanged). Six mutants replayed, all killed. Still to come: the fresh harvest, the run, its certification (hardware, owner).

## 2026-11-06

Hardware session, 2026-11-07 UTC, run on the owner's go-ahead. Harvest: 100,000 shots on qubit 8, 44,920 bits, min-entropy estimate 0.8997 per shot, kept outside git in ~/.local/share/fairest-coin/runs/2026-11-07-dbn986c4148s7390hohg until its batch is spent. Readout, 10,000 shots each way: data/runs/2026-11-07-dbn9c3k4148s7390htjg and -dbn9ca44148s7390htqg (34 and 43 of 156 qubits within 3σ of published). Prediction: data/predictions/2026-11-07T030927-chsh-ibm_marrakesh.json.gz, pair 153-154, 22,000 rounds, S = 2.755 ± 0.020, 95% interval [2.715, 2.796], settings from 44,000 bits of that batch (920 remain). The CLI printed [2.717, 2.789], the interval of its throwaway validating plan; the file is the prediction.
