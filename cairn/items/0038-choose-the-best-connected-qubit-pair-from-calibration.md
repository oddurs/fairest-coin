---
id: 38
uid: 81387cca-665b-427a-b867-be40a1649bf4
title: Choose the best-connected qubit pair from calibration
type: feature
status: backlog
milestone: v0.4
depends_on:
- 21
- 37
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: s
area: compile
---

## Problem

Which two qubits run the Bell test decides how close S gets to its ideal. Choosing the
pair is routing in miniature.

## Proposal

`select_pair(calibration, readout, coupling_map)` scores every coupled pair by predicted Bell
fidelity from the noise model (two-qubit gate error plus both readout errors) and returns
the best, with the score. The readout comes from `coin run readout` in the same session,
not from the published calibration: spike 0069 found published p(1|0) correlates only
+0.46 with measured, and that readout breaks transiently (qubit 59: 75% for a while).

## Acceptance criteria

- [ ] On a calibration fixture, returns the pair a brute-force density simulation ranks first
- [ ] Only coupled pairs are ever considered
- [ ] Readout errors come from readout runs (`readout.measured`), with the published values used only where a qubit was not measured, and the source of each is reported
- [ ] `coin predict --pairs` lists the top 5 pairs with predicted fidelity
