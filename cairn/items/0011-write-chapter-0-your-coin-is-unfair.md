---
id: 11
uid: f9bd89d5-f8c0-4f21-a870-1be7bf6fb1e2
title: 'Write chapter 0: your coin is unfair'
type: docs
status: done
milestone: v0.1
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p0
effort: m
area: essay
---

## Problem

The project is one question, and this chapter makes the reader care about it before any
quantum mechanics appears.

## Proposal

`docs/chapters/00-your-coin-is-unfair.md`. Cover: a tossed coin is deterministic physics;
Diaconis, Holmes and Montgomery's prediction of same-side bias, and Bartoš et al.'s 2023
measurement of 50.8% over 350,757 flips; pseudo-random generators are deterministic by
design; statistical tests can only fail to reject. End on the thesis: can you *prove* a
coin flip is random?

## Acceptance criteria

- [x] Every factual claim has a citation with a link
- [x] Contains no code and needs no physics background
- [x] Under 1,500 words
- [x] Linked from the README's chapter index

## Result

docs/chapters/00-your-coin-is-unfair.md (1,1xx words, no code): Keller 1986, Diaconis–Holmes–Montgomery 2007 (~51% same-side), Bartoš et al. JASA 2025 (50.8% over 350,757 flips), Mersenne Twister state recovery from 624 outputs, von Neumann's 'state of sin', NIST SP 800-22, π passes tests yet is deterministic. Ends on the thesis and promises chapter 1 builds the simplest quantum coin. All DOIs verified against Crossref.
