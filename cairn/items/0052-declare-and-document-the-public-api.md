---
id: 52
uid: 4af44c9d-9580-4b3e-982d-5062e986a8f5
title: Declare and document the public API
type: docs
status: backlog
milestone: v1.0
depends_on:
- 44
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: tooling
---

## Problem

v1.0 is the API we agree to be held to. Right now everything is implicitly public.

## Proposal

`__all__` in each module, private names prefixed with an underscore, a docstring on every
public name, and an API section in the README.

## Acceptance criteria

- [ ] A test fails if a name is added to `__all__` without a docstring
- [ ] The README's API section lists every public module and what it is for
