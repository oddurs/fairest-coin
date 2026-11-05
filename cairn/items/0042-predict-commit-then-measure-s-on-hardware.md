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

- [ ] Submission refuses while the prediction is uncommitted, with a message saying so
- [ ] The prediction states S and an interval, and the result says whether the measured S fell inside it
- [ ] Archived run reports S, its standard error, and S_low at the stated ε
- [ ] S is also reported for each half of the run, so drift during the job is visible
- [ ] The prediction commit is an ancestor of the result commit in the git history

## 2026-11-05

Code first, in its own PR, because squash merges would erase a branch-only prediction commit from main's history. coin run chsh now has three modes: --dry-run; --predict (needs --readout; writes the whole plan, with the calibration snapshot, every round's setting, predicted S, its standard error and a 95% interval, to data/predictions/<time>-chsh-<backend>.json.gz); --submit --prediction FILE (commitment.committed refuses a file git does not track or that changed since its last commit; the run then archives committed_as and prediction_file). The interval (chsh.s_interval, INTERVAL_DRAWS = 400): readout errors from Beta posteriors given the readout runs' counts, the cz error scaled log-uniformly in [1/2, 2] (no error bar is published: an assumption, stated in the file), plus sampling scatter at the run's rounds; seeded from the choices so the file reproduces it; endpoints move < 0.01 across seeds. load_prediction refuses a file whose program hash differs from what this version would run. chsh_report adds the interval verdict, S for each half, and the commit. Seven mutants replayed, all killed (one after adding a test pinning both verdicts).
