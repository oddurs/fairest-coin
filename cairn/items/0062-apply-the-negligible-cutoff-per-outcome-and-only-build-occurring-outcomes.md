---
id: 62
uid: a858a109-5e90-47c7-8f75-98be3a202dc7
title: Apply the negligible cutoff per outcome, and only build occurring outcomes
type: bug
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p1
effort: s
area: sim
---

## What happens

`probabilities()` drops basis indices below `NEGLIGIBLE` before summing them into
outcomes, but its docstring promises to drop whole outcomes. An outcome spread over many
tiny basis amplitudes would vanish and the result would not sum to 1. Separately,
`_outcome_strings` builds all 2ⁿ outcome strings in Python on every call although only
the occurring indices are looked up.

## What should happen

Sum per outcome first, then drop outcomes at or below `NEGLIGIBLE`. Build outcome strings
only for indices with nonzero probability or counts.

## Reproduction

1. Read `src/coin/sim.py` `probabilities`: the filter is on `born > NEGLIGIBLE` per index.
2. A test with an outcome split across many sub-cutoff amplitudes demonstrates it.

Found by the v0.1 milestone review; defect in 0009.

## 2026-11-01

20-qubit circuit, same machine: probabilities 1.326s → 0.036s, sample 1.333s → 0.046s, because outcome strings are now built only for occurring basis states. The per-outcome cutoff bug needs ~40 qubits to show naturally, so its test raises NEGLIGIBLE to 0.3 via monkeypatch; it returned {} before the fix.

## Result

coin.sim: probabilities() sums basis states per outcome, then drops outcomes ≤ NEGLIGIBLE; outcome strings are built per occurring index by _outcome(index, readout, n), with _readout(circuit) mapping clbit → last-measured qubit. ~37× faster at 20 qubits.
