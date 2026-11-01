---
id: 1
uid: 99001bcf-2696-4f63-88e8-5beb0b6770b8
key: v0.1
title: The ideal coin
type: milestone
status: done
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p2
due: 2026-11-08
---

## Ships

`coin flip --sim` flips a coin on a simulator written from scratch, and chapters 0–1
explain why a coin is worth asking about and what a quantum coin is.

## Done when

- [x] `uv tool install git+https://github.com/oddurs/fairest-coin` gives a working `coin`
- [x] `coin flip --sim` prints HEADS or TAILS; `--shots 10000` lands within 3σ of 50/50
- [x] The simulator handles n qubits with one- and two-qubit gates, covered by property tests
- [x] Chapters 0 and 1 are in `docs/chapters/` and linked from the README
- [x] Tagged `v0.1.0` with a changelog entry

## Explicitly not in this milestone

- Noise of any kind: the ideal coin is the baseline everything later is compared to
- Real hardware, accounts, or API keys
- Figures: there is no data yet to draw

## 2026-11-01

Verified on the tagged release: install from git@v0.1.0 works; 10,000 seeded shots gave 4,971 heads, 0.58σ from 5,000; the simulator's property tests cover random circuits of up to 6 qubits with one- and two-qubit gates on arbitrary pairs; chapters 0 and 1 are linked from the README; v0.1.0 tag and release exist.
