---
id: 76
uid: ce25fd4f-05ec-47c3-b011-546f0fc16cfe
title: Scrub encoded credentials and check classical bits in the IBM adapter
type: bug
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p2
effort: s
area: hardware
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. Credential scrubbing is a plain string replace, so a URL-encoded instance id in an
error message passes through. The check that the transpiled circuit is unchanged compares
gate names, angles and physical qubits but not classical bits, so a remapped measurement
would go unnoticed.

## Acceptance criteria

- [x] URL-encoded (and percent-encoded twice) forms of the token and instance are scrubbed (test)
- [x] A circuit whose measurements land in different classical bits is refused as changed (test)

## Result

The adapter scrubs the token and instance verbatim, percent-encoded once and twice (either hex case) and form-encoded; the circuit-change check compares classical bits as well as gates, angles and physical qubits.
