---
id: 81
uid: a422d64c-ef6c-4b42-8e50-c534363ae8ce
title: Close the four test gaps the review's mutants found
type: chore
status: backlog
milestone: v0.3.1
created: 2026-11-02
updated: 2026-11-02
priority: p2
effort: s
area: tooling
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. Four wrong changes survived the suite: dividing a readout run's counts by the other
run's shots; accepting a readout worse than random; computing drift variance from one half;
dropping published readouts at or above 0.5 from the readout plan.

## Acceptance criteria

- [ ] Each of the four mutants fails at least one test
