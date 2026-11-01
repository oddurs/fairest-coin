---
id: 37
uid: 84db55b0-c73f-4d2c-9101-866b6050eaa9
title: Lower two-qubit gates to the backend's native entangler
type: feature
status: backlog
milestone: v0.4
depends_on:
- 20
created: 2026-11-01
updated: 2026-11-01
priority: p0
effort: m
area: compile
---

## Problem

The Bell circuit's CX is not native hardware either; it must become the backend's
entangling gate (CZ or ECR, per the IBM spike) plus single-qubit gates.

## Proposal

Extend `coin/compile.py`: rewrite CX in terms of the native two-qubit gate, then
re-optimise single-qubit runs. Two-qubit gates on uncoupled physical qubits raise an error
rather than being routed: we never route.

## Acceptance criteria

- [ ] Property test: lowered two-qubit circuits equal the originals up to global phase
- [ ] The Bell circuit lowers to exactly one native two-qubit gate
- [ ] A gate on an uncoupled pair raises `ValueError` naming both qubits
