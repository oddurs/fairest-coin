---
id: 31
uid: 37f20150-c6d8-4342-8e08-9807278e694b
title: Build a randomness test battery from scratch
type: feature
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: m
area: extract
---

## Problem

We need to show that raw bits fail where the bias says they should, that extracted bits
pass, and that passing proves nothing.

## Proposal

`coin/tests_random.py`: frequency (monobit), block frequency, runs, longest run of ones,
and serial tests after NIST SP 800-22, each returning a p-value. Implemented from the
specification using only `math` and numpy, since writing them is the lesson.

## Acceptance criteria

- [x] Each test reproduces the worked example in NIST SP 800-22 to the published p-value
- [x] A bias of 0.51 over 10⁶ bits fails monobit; the same bits after von Neumann pass
- [x] Digits of π, which are deterministic, pass the battery, and a test documents it as the punchline

## 2026-11-01

Negative control from spike 0028: von Neumann applied to qubit 88's shots in data/runs/2026-11-02-dbjuh5d6p51s73cljo60 gives about 25,000 bits that are fair but serially correlated (+9.8σ at lag 1). The serial test should fail them; the monobit test will pass them.

## 2026-11-01

Real negative control, data/runs/2026-11-02-dbjuh5d6p51s73cljo60: von Neumann on qubit 88 gives 25,503 bits that pass monobit (p=0.27) and block frequency (0.33) but fail runs (1.5e-22), longest run (1.6e-14) and serial (4.3e-38; second difference 5.4e-19). The same on qubit 10 (25,128 bits) passes all six (lowest p=0.31). Fair is not independent, and only the pattern tests see it.

## 2026-11-01

Evidence, tests/test_battery.py. (1) SP 800-22's worked examples reproduced to the six published digits: monobit 0.527089 and 0.109599, block frequency 0.801252 and 0.706438, runs 0.147232 and 0.500798, longest run 0.180609, serial 0.808792 and 0.670320. The §2 100-bit example equals pi_bits(100). (2) 51% tails over 10⁶ bits: monobit p < 1e-50; von Neumann's output of the same bits passes. (3) 10⁶ bits of π pass all six. Longest-run class probabilities are counted exactly: they match NIST's code at M=8 (exact) and M=128 (9 digits); SP 800-22's M=10,000 table is off by up to 0.0016. Review fixed two crashes (serial on short sequences through float rounding; runs on short constant input), each with a test seen to fail on a mutant.

## Result

coin.battery: monobit, block frequency, runs, longest run, serial (two p-values), igamc, battery/passes at α = 0.01, and pi_bits (10⁶ bits in ~1 s), which passes. On the chip map, von Neumann's output for qubit 88 passes monobit but fails runs, longest run and serial; qubit 10's passes all.
