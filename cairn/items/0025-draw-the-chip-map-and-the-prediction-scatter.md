---
id: 25
uid: 1c662b70-c98d-4d80-9de1-5b6119cd343e
title: Draw the chip map and the prediction scatter
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 23
- 24
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] Both come from the archived chip-map run only
- [x] Error bars are binomial standard errors for the run's shot count
- [x] Qubits more than 3σ off their prediction are labelled

## 2026-11-01

Labelling: 119 of 150 qubits are more than 3σ off, so naming them all would bury the plot. Every one is marked (hollow grey against filled blue), and those more than 5 percentage points off their prediction are named by qubit. The chip-map layout is derived from the archived calibration's two-qubit gates (heavy_hex_layout), tested to put every coupled pair one unit apart. Colour is clipped at ±5%; the 10 qubits beyond it are named in the caption.

## Result

docs/figures/chip-map.svg and prediction-scatter.svg, rendered from data/runs/2026-11-02-dbjuh5d6p51s73cljo60 by coin.figures. chipmap.compare(run) gives each predicted qubit's QubitResult (predicted, alternative, measured, sigma, z) for the chapter to quote.
