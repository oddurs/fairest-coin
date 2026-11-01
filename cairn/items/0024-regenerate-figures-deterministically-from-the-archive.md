---
id: 24
uid: 2450d34a-04b8-4902-b7d9-906f577cf23c
title: Regenerate figures deterministically from the archive
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 19
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p1
effort: s
area: figures
---

## Problem

A figure that cannot be regenerated is a claim, not evidence. Figures must come from the
archive and nothing else.

## Proposal

`scripts/figures` renders every figure under `docs/figures/` from `data/runs/` with
matplotlib (optional `figures` dependency group), as SVG with fixed metadata so the output
is byte-stable. `scripts/task` gains nothing; CI runs it as part of `build`.

## Acceptance criteria

- [x] Running it twice produces byte-identical files
- [x] CI fails if the committed figures differ from the regenerated ones
- [x] Figures render legibly on both light and dark GitHub themes

## 2026-11-01

Module is src/coin/figures.py (registry FIGURES: file name -> function(runs_dir) -> Figure); only it imports matplotlib, and a subprocess test imports every other coin module and asserts matplotlib stays out of sys.modules. matplotlib 3.11.2 sits in the 'figures' dependency group and [tool.uv] default-groups = [dev, figures], so every uv sync (CI, scripts/setup, hooks) carries it without a ci.yml change; the wheel never depends on it. Byte-stability: svg.fonttype none, svg.hashsalt fixed, metadata Date None, fixed figsize/dpi, explicit subplots_adjust (no tight bbox), font.family DejaVu Sans so matplotlib's bundled font wins ties over system copies. Evidence: two renders give sha1 identical files on macOS; a Linux container (python3.13-bookworm, arm64, system fonts-dejavu-core installed) passes --check against the macOS render. Legibility: transparent background, text/axes #7a7a7a (about 4.3:1 on white and on #0d1117), series #3a80dc/#e2622d pass the dataviz validator (lightness band, chroma, CVD dE 25, 3:1 contrast) on both surfaces; checked by rasterising with rsvg-convert on white and #0d1117, not in GitHub itself. Text is drawn by the viewer's font, so two-line row labels can sit a few px off where its metrics differ from DejaVu. --check: scripts/task build fails naming the file when a committed SVG is altered (verified, exit 1), missing, or an extra file exists in docs/figures.

## Result

scripts/figures renders every figure in src/coin/figures.py's FIGURES registry from data/runs into docs/figures as byte-stable SVG; to add a figure write function(runs_dir) -> matplotlib Figure, register its file name in FIGURES, run scripts/figures, commit the SVG. scripts/figures --check (run by scripts/task build, hence check and CI) renders to a temp dir and fails non-zero naming each committed file that differs byte-for-byte, is missing, or is not produced by any figure. First figure: docs/figures/first-coin.svg, measured vs predicted tails fraction with 1 sigma for the first run.
