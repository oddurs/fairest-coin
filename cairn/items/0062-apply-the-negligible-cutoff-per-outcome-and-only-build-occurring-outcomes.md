---
id: 62
uid: a858a109-5e90-47c7-8f75-98be3a202dc7
title: Apply the negligible cutoff per outcome, and only build occurring outcomes
type: bug
status: backlog
milestone: v0.2
created: 2026-11-01
updated: 2026-11-01
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
