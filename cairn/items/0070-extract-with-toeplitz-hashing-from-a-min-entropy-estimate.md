---
id: 70
uid: db019e14-aa34-4a16-a646-95b0910bbff8
title: Extract with Toeplitz hashing from a min-entropy estimate
type: feature
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
depends_on:
- 28
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] `toeplitz` matches an explicit matrix-vector product over GF(2) for random small sizes (property test)
- [x] On synthetic sources whose min-entropy is known (biased i.i.d., and a Markov chain), `min_entropy` never exceeds the true value
- [x] Output length follows the leftover hash lemma for a stated ε, and the code refuses to output more
- [x] On qubit 88's shots from data/runs/2026-11-02-dbjuh5d6p51s73cljo60, the Toeplitz output passes the 0031 battery's serial test where von Neumann's output fails it

## 2026-11-01

Evidence, tests/test_extract.py. (1) Hypothesis: toeplitz equals the explicit Toeplitz matrix product mod 2 for n, m ≤ 40; exact at 4000×3000 against an int64 product, and at n = m = 1,000,001 all-ones (largest sums). An independent reviewer checked n = m = 10⁶ dense against an exact chunked convolution: bit-identical; rounding 2e-9. (2) min_entropy ≤ truth for i.i.d. bias 0.5–0.99, Markov stay 0.01–0.99, telegraph 0.2/0.8, cycling bias periods 2/3/8/200, order-2 copying, exact periods, repeated blocks. (3) Length ⌊n·h − 64⌋ checked against a hand value (49,936) and refused above it. (4) Qubit 88: von Neumann output fails serial; Toeplitz output passes the battery. Two adversarial reviews: the first broke a three-estimate version with periodic/higher-order sources (fixed with lag, online Markov and phase predictors); the second found hidden-state sources overstated up to 1.77× (telegraph dwell 5–200, drifting-period cycles, intermittent alternation). Extraction now spends SAFETY = ½ of the estimate, which covers every source found; the miss stays visible in tests. Hardware (chip map): estimate 0.889/0.434/0.892/0.548/0.902 for qubits 88/34/36/48/10.

## Result

coin.extract: min_entropy (most common value, worst block, Markov cycle, lag ≤1024, online Markov order ≤16, phase P ≤256; all 99.5% bounds), secure_length, toeplitz (FFT, exact), seed_bits, toeplitz_extract → Extraction(bits, entropy_per_bit, estimate, epsilon, input_bits, seed_used). By default spends SAFETY = ½ of the estimate. The guarantee is conditional on the source being within reach of the estimate and margin; π shows no estimate can be unconditional.
