---
id: 42
uid: 9399aeb3-ac08-4c8f-853d-670397dcc4b7
title: Predict, commit, then measure S on hardware
type: feature
status: doing
milestone: v0.4
assignee: Oddur Sigurdsson
claimed: 2026-11-05
depends_on:
- 38
- 40
- 41
created: 2026-11-01
updated: 2026-11-05
priority: p0
effort: m
area: chsh
qpu: 'true'
---

## Problem

The Bell test is the climax, and it is only convincing if the prediction was made in
public, before the run.

## Proposal

`coin run chsh --backend NAME` computes the predicted S for the selected pair, with an
interval from the uncertainty of its inputs (measured readout, published two-qubit error),
writes both to `prediction.json`, and refuses to submit until that file is committed to git.
Then it runs the design from the CHSH spike and archives the result.

## Acceptance criteria

- [x] Submission refuses while the prediction is uncommitted, with a message saying so
- [x] The prediction states S and an interval, and the result says whether the measured S fell inside it
- [x] Archived run reports S, its standard error, and S_low at the stated ε
- [x] S is also reported for each half of the run, so drift during the job is visible
- [ ] The prediction commit is an ancestor of the result commit in the git history

## 2026-11-05

Code first, in its own PR, because squash merges would erase a branch-only prediction commit from main's history. coin run chsh now has three modes: --dry-run; --predict (needs --readout; writes the whole plan, with the calibration snapshot, every round's setting, predicted S, its standard error and a 95% interval, to data/predictions/<time>-chsh-<backend>.json.gz); --submit --prediction FILE (commitment.committed refuses a file git does not track or that changed since its last commit; the run then archives committed_as and prediction_file). The interval (chsh.s_interval, INTERVAL_DRAWS = 400): readout errors from Beta posteriors given the readout runs' counts, the cz error scaled log-uniformly in [1/2, 2] (no error bar is published: an assumption, stated in the file), plus sampling scatter at the run's rounds; seeded from the choices so the file reproduces it; endpoints move < 0.01 across seeds. load_prediction refuses a file whose program hash differs from what this version would run. chsh_report adds the interval verdict, S for each half, and the commit. Seven mutants replayed, all killed (one after adding a test pinning both verdicts).

## 2026-11-05

Prediction, 2026-11-05 21:52 UTC: data/predictions/2026-11-05T215257-chsh-ibm_marrakesh.json.gz. Readout measured the same session (10,000 shots each way, data/runs/2026-11-05-dbmfl0t8mdtc73d7sq4g and -dbmfl6674qds73ds7bkg; only 34 and 44 of 156 qubits read within 3σ of their published error). With it the best pair is 153-154 (qubit 5 now misreads |0⟩ 6% of the time, so 5-6 fell back). Predicted S = 2.765 ± 0.026 at 12,000 rounds, 95% interval [2.713, 2.815], about 14 QPU s. Merged to main before the run, in its own PR.

## 2026-11-05

Result, run by the owner 2026-11-05 22:03 UTC: data/runs/2026-11-05-dbmfqed8ft8s738upl80, ibm_marrakesh 153-154, 12,000 rounds, 7 QPU s (≈ 2 s + 0.42 ms per swept round, better than spike 0040's rough 1 ms). S = 2.738 ± 0.027 against 2.765 predicted (z = −1.0), inside the committed 95% interval [2.713, 2.815]. S_low = 2.495 at ε = 2.3 × 10⁻¹⁰. Halves 2.775 ± 0.037 and 2.701 ± 0.038 (difference 1.4σ: no clear drift). Correlations +0.674, +0.687, +0.699, −0.678 against ±0.690–0.692 predicted. Twirling and dynamical decoupling off. Predicted 21:52:57, committed on main as c86a39c (#80), submitted 22:03:37; the run records committed_as = c86a39c.
