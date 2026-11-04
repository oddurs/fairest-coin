---
id: 74
uid: 0ff88171-f3d0-4d94-a69d-ed109f368667
key: v0.3.1
title: Hardening
type: milestone
status: done
created: 2026-11-02
updated: 2026-11-04
closed_at: 2026-11-04
priority: p2
due: 2026-11-09
---

## Ships

v0.3.1: every defect found by the review of the first three milestones is fixed, the essay
says what the data now shows, and the v0.4 plan is rebuilt on what v0.2 and v0.3 learned.

## Done when

- [ ] No path loses a submitted job's shots, prediction or calibration
- [x] The min-entropy estimate and the harvest pre-flight agree on every shot count
- [ ] Every claim in the README and chapters 0–3 matches the archive and the later spikes
- [x] The v0.4 items are consistent with the hardware findings and with what certification needs
- [x] Tagged `v0.3.1`

## 2026-11-04

Shipped as v0.3.1 on 25ab32b. Criteria 2, 4 and 5 hold: 0077 pre-flights harvests with the estimator itself; 0084 rebuilt v0.4; the tag exists. Criteria 1 and 3 were met as far as the first review saw, but the review of v0.3 as released (2026-11-04) found more: archive writes a power cut can lose and recovery that trusts others' records (0089, 0090), and four essay and README claims that do not match the archive (0093). They are left unticked and carried to v0.3.2 (0087).

## Result

v0.3.1 released. Two criteria proved incomplete after release and moved to v0.3.2 (0087): durable archive writes and recovery (0089, 0090), and essay corrections (0093).
