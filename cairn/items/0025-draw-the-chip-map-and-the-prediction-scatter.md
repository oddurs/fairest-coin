---
id: 25
uid: 1c662b70-c98d-4d80-9de1-5b6119cd343e
title: Draw the chip map and the prediction scatter
type: feature
status: backlog
milestone: v0.2
depends_on:
- 23
- 24
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: figures
---

## Problem

Chapter 2's result is visual: where on the chip the coin is unfair, and how close the
prediction came.

## Proposal

Two figures: the measured bias of each qubit laid out on the backend's coupling graph, and
predicted against measured bias per qubit with the y = x line and binomial error bars.

## Acceptance criteria

- [ ] Both come from the archived chip-map run only
- [ ] Error bars are binomial standard errors for the run's shot count
- [ ] Qubits more than 3σ off their prediction are labelled
