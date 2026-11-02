---
id: 79
uid: 527120ae-3d5e-437e-ba81-82e17bbe2fd4
title: Report a chip map whose calibration had no readout length
type: bug
status: backlog
milestone: v0.3.1
created: 2026-11-02
updated: 2026-11-02
priority: p2
effort: s
area: hardware
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. `plan` accepts a calibration without `readout_length` and leaves the alternative
predictions empty; `coin compare` on such a run then crashes on an empty median.

## Acceptance criteria

- [ ] `coin compare` reports such a run, saying the alternative was not predicted (test)
