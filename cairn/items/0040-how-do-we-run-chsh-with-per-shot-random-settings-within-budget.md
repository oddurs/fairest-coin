---
id: 40
uid: 415c84b9-0acd-4aa7-b7f1-2fc41f2eef57
title: How do we run CHSH with per-shot random settings within budget?
type: spike
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 39
created: 2026-11-01
updated: 2026-11-06
closed_at: 2026-11-05
priority: p0
effort: s
area: chsh
qpu: 'true'
---

## Question

How do we give each shot its own measurement settings without one job per shot, and how
many shots do we need for S > 2 at 5σ, given the fidelity we predict for the best pair?

## Why it has to be answered before the work

Per-shot settings chosen by our own coin are what make the bootstrap honest, and the
naive implementation would spend the whole allowance on job overhead.

It also has to interleave the four setting pairs through the job, so that drift (spike 0028
found qubits that change within seconds) affects every correlator alike rather than biasing
whichever setting ran last.

## Options

- One parametrised circuit, with all settings as one parameter array in a single Sampler call
- Four fixed-setting circuits, with the settings sequence applied afterwards (weaker: settings are not chosen per shot before measurement)

Either way the settings are in the job before it runs, so the device could in principle see
them: a freedom-of-choice loophole this project cannot close, to be named in chapter 5 and
the epilogue.

## What would settle it

A submitted test job with 100+ parameter sets, its QPU seconds read back, and a shot count
derived from the standard error of S ≈ √(Σ(1 − Eᵢ²)/Nᵢ) at the predicted correlators.

## Answer

One parametrised circuit, one row per shot. The four settings are lowered onto one native
skeleton (H on each qubit, the `cz`, then rz·sx·rz·sx·rz on each), so they differ only in
four `rz` angles, which are free on hardware and become `input float[64]` parameters. One
Sampler call binds a row per round with one shot each; the rows run in order, so the settings
are interleaved through the job and every round's choice is archived with its shot.

The test job (data/runs/2026-11-05-dbmeqi58mdtc73d7rk3g, ibm_marrakesh pair 5–6, 2,000 rounds,
settings from the operating system's generator) cost 4 QPU seconds; a plain 10,000-shot job
the same day cost 5. With about 2 s per job, a swept round costs roughly 1 ms, four times a
plain shot, and still cheap: QPU ≈ 2 s + 1 ms per round, from one job and whole-second charges.

It measured S = 2.756 ± 0.065 against 2.777 predicted (z = −0.3), S_low = 2.160 at
ε = 2.3 × 10⁻¹⁰, and S = 2.754 and 2.764 in its two halves.

Shots: the Hoeffding bound clears 2 when 8·√(ln(1/ε)/2n) < S − 2. At S ≈ 2.75 and ε = 2⁻³²
that is about 1,300 rounds; S_low ≥ 2.5 takes about 11,000 (≈ 13 QPU s). The standard
error √(Σ(1 − Eᵢ²)/Nᵢ) is 0.065 at 2,000 rounds and falls as 1/√n.

The settings are in the job before it runs, so the device could in principle see them: the
freedom-of-choice loophole this project cannot close, for chapter 5 and the epilogue.

## 2026-11-05

Built the path, not a throwaway script, so the test job was predicted and archived like any run: compile.zxzxz and compile.sweep_qasm (SweptProgram), chsh.setting_circuits and chsh.SETTINGS, chsh.counts_by_setting and correlations_by_setting, hardware.Sweep on Submission (validated; the pending record and meta.json keep one digit per shot as choices), Transport.run(..., parameter_values=rows), the adapter binding one row per shot and comparing a parameter by name, bell.plan_chsh / chsh_summary / chsh_report, coin run chsh, and coin compare for CHSH runs. Six mutants replayed, all killed. The adapter's local test runs a 200-row sweep through Aer. On hardware the 2,000-row job's memory came back one bitstring per row, in order.

## Result

One parametrised program with a row per round: the four settings share a native skeleton and differ only in free rz angles. 2,000 swept rounds cost 4 QPU s (≈ 2 s + 1 ms per round) and gave S = 2.756 ± 0.065 (predicted 2.777), S_low = 2.160 at ε = 2⁻³². About 1,300 rounds clear 2 at that ε; 11,000 put S_low at 2.5.

## 2026-11-06

Superseded on cost: with 0042's and 0043's jobs (12,000 and 22,000 rounds, 7 and 9 s), a swept job costs about 3.5 s plus 0.25 ms a round, the same per-round rate as a plain shot. The 1 ms above came from one small job with whole-second charges.
