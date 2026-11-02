---
id: 79
uid: 527120ae-3d5e-437e-ba81-82e17bbe2fd4
title: Report a chip map whose calibration had no readout length
type: bug
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p2
effort: s
area: hardware
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. `plan` accepts a calibration without `readout_length` and leaves the alternative
predictions empty; `coin compare` on such a run then crashes on an empty median.

## Acceptance criteria

- [x] `coin compare` reports such a run, saying the alternative was not predicted (test)

## Result

coin compare reports a chip map with no alternative predictions (— in that column, and a line saying why); correlations print — when undefined. Output for runs with both predictions is unchanged (chapter 2's console test).
