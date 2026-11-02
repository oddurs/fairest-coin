---
id: 68
uid: 158d3f6d-1bd6-4e40-a5b1-e190be5db508
title: Gzip counts and memory so whole-chip runs fit in git
type: feature
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
depends_on:
- 19
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: s
area: hardware
---

## Problem

A whole-chip run measures 156 qubits at up to 100,000 shots. Nearly every 156-bit outcome is
unique, so `counts.json` and `memory.txt` would each be about 16 MB of text per run, too much
to commit for every chip map.

## Proposal

New runs write `counts.json.gz` and `memory.txt.gz` (gzip with mtime 0, so the bytes depend
only on the data). The loader reads either the plain or the gzipped form, so the first run,
which is immutable, still loads exactly as it is. Writing both forms of one file is refused
on load as ambiguous.

## Acceptance criteria

- [x] A 100,000-shot, 156-qubit synthetic run archives in under 6 MB
- [x] The first archived run loads unchanged
- [x] A directory holding both `counts.json` and `counts.json.gz` is refused, naming both
- [x] Round trip of a gzipped run gives an equal `Run`

## 2026-11-01

Measured: a synthetic 100,000-shot, 156-qubit run archives in 4.7 MB (memory 2.33 MB, counts 2.40 MB gzipped) and round-trips equal. gzip level 6, not 9: level 9 took 88 s on 16 MB of random bits (145 s for write_run), level 6 2.7 s for a 6% larger file. While building this, the compile suite's flake recurred and its cause was found (hypothesis deadline vs Qiskit's cold first parse); the fix is in 0067.

## Result

New runs write counts.json.gz and memory.txt.gz (gzip level 6, mtime 0); load_run reads plain or gzipped and refuses a run holding both forms. A 100,000-shot, 156-qubit run archives in ~4.7 MB. The first run loads unchanged.
