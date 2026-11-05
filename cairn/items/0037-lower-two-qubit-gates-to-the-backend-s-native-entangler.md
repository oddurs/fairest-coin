---
id: 37
uid: 84db55b0-c73f-4d2c-9101-866b6050eaa9
title: Lower two-qubit gates to the backend's native entangler
type: feature
status: done
milestone: v0.4
assignee: Oddur Sigurdsson
depends_on:
- 20
created: 2026-11-01
updated: 2026-11-05
closed_at: 2026-11-05
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

- [x] Property test: lowered two-qubit circuits equal the originals up to global phase
- [x] The Bell circuit lowers to exactly one native two-qubit gate
- [x] A gate on an uncoupled pair raises `ValueError` naming both qubits

## 2026-11-01

From spike 0015: the native two-qubit gate on all three backends is cz.

## 2026-11-05

lower() turns each cx into one cz, folding the Hadamards on the target into the single-qubit runs either side, so they merge with neighbouring gates (the Bell circuit H, CX becomes rz sx rz on each qubit around one cz). compile.coupled_pairs(calibration) reads the cz entries (176 pairs on ibm_marrakesh, the heavy-hex edge count); compile.require_coupled refuses a two-qubit gate whose physical pair is not among them, naming both qubits, and Submission calls it, so an uncoupled pair is refused before anything reaches IBM. The test workaround native_only, which did by hand what lower now does, is gone. Five mutants replayed (each Hadamard dropped, the pair ordered, any two-qubit gate counted as coupling, Submission unchecked): all killed.

## Result

lower() writes each cx as one native cz with its Hadamards merged into the neighbouring single-qubit runs (property-tested against the original unitary; the Bell circuit costs one cz); Submission refuses a two-qubit gate on a pair the calibration does not couple, naming both physical qubits; nothing is routed.
