---
id: 18
uid: 1096ef10-f133-4e95-8f8b-6c923b0e0769
title: Which error sources dominate a one-gate coin?
type: spike
status: backlog
milestone: v0.2
depends_on:
- 15
- 17
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: noise
---

## Question

For H followed by measurement on a typical IBM qubit, how much of the bias comes from
readout asymmetry, from T1 decay during the measurement window, and from gate error?

## Why it has to be answered before the work

It decides what the calibration-to-noise-model mapping must include, and it is the
prediction chapter 2 makes before any hardware is touched.

## Options

- Readout asymmetry alone (simplest model)
- Readout plus thermal relaxation over the gate and measurement durations
- Everything, including the reported gate error as depolarizing

## What would settle it

Sweep each source over the ranges published in real calibration data with the density
simulator, and tabulate its contribution to P(1) − 0.5.

## Answer

<!-- Filled in when the spike closes. -->
