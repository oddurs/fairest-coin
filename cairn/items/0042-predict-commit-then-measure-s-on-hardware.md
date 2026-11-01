---
id: 42
uid: 9399aeb3-ac08-4c8f-853d-670397dcc4b7
title: Predict, commit, then measure S on hardware
type: feature
status: backlog
milestone: v0.4
depends_on:
- 38
- 40
- 41
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: chsh
qpu: 'true'
---

## Problem

The Bell test is the climax, and it is only convincing if the prediction was made in
public, before the run.

## Proposal

`coin run chsh --backend NAME` computes the predicted S for the selected pair, writes it to
`prediction.json`, and refuses to submit until that file is committed to git. Then it runs
the design from the CHSH spike and archives the result.

## Acceptance criteria

- [ ] Submission refuses while the prediction is uncommitted, with a message saying so
- [ ] Archived run reports S, its standard error, and σ above 2
- [ ] The prediction commit is an ancestor of the result commit in the git history
