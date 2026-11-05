---
id: 38
uid: 81387cca-665b-427a-b867-be40a1649bf4
title: Choose the best-connected qubit pair from calibration
type: feature
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 21
- 37
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
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

- [x] On a calibration fixture, returns the pair a brute-force density simulation ranks first
- [x] Only coupled pairs are ever considered
- [x] Readout errors come from readout runs (`readout.measured`), with the published values used only where a qubit was not measured, and the source of each is reported
- [x] `coin predict --pairs` lists the top 5 pairs with predicted fidelity

## 2026-11-05

New coin.chsh: the CHSH circuit (Alice 0, π/2; Bob ±π/4, read along X–Z axes by RY(−θ)), correlation, s_value, predict_s (noisy density simulation of the four lowered circuits: relaxation plus depolarizing per gate, the cz's depolarizing sized for d = 4 as Aer does; then each qubit's readout), and rank_pairs(calibration, measured) — named for what it returns, a ranking, the first being the selection. noise gains pair_depolarizing, pair_gate_depolarizing and pair_gates (each pair's cz, the worse direction, failed ones left out). Checked against an analytic model, depolarizing plus readout only: S = c_A·c_B·2√2·(1 − 4r/3) + 2·d_A·d_B, agreeing to 1e-9 on every pair of a fixture where neither the best cz nor the best readout picks the winner. On ibm_marrakesh (second chip map's calibration, readout measured 2026-11-02): 158 pairs scored in 1.3 s; best 43–44 at S = 2.762, then 43–56, 47–57, 5–6, 148–149; with published readout the order changes (54–55 first). Seven mutants replayed: six killed, one equivalent (pairs with a usable cz are exactly the coupled ones), which led to removing the redundant filter.

## Result

coin.chsh.rank_pairs scores every coupled pair by the CHSH S its noise model predicts (density simulation, measured readout where given, the source reported) and returns them best first; coin predict --pairs [--readout ZERO ONE] lists the top 5. Agrees with an analytic model to 1e-9; on ibm_marrakesh the best pair was 43–44 at S = 2.76.
