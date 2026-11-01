---
id: 40
uid: 415c84b9-0acd-4aa7-b7f1-2fc41f2eef57
title: How do we run CHSH with per-shot random settings within budget?
type: spike
status: backlog
milestone: v0.4
depends_on:
- 39
created: 2026-11-01
updated: 2026-11-01
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

## Options

- One parametrised circuit, with all settings as one parameter array in a single Sampler call
- Four fixed-setting circuits, with the settings sequence applied afterwards (weaker: settings are not chosen per shot before measurement)

## What would settle it

A submitted test job with 100+ parameter sets, its QPU seconds read back, and a shot count
derived from the standard error of S ≈ √(Σ(1 − Eᵢ²)/Nᵢ) at the predicted correlators.

## Answer

<!-- Filled in when the spike closes. -->
