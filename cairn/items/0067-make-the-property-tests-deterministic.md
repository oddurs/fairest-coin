---
id: 67
uid: 888da86a-1387-487c-bd46-9c50f226690a
title: Make the property tests deterministic
type: chore
status: backlog
milestone: v0.2
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: tooling
---

## Problem

The compile suite failed once locally and the failure never reproduced across 48 further runs
and 40 explicit hypothesis seeds. Hypothesis draws fresh examples each run, so a property test
can fail on a rare input and pass on the retry, which breaks the project rule that no test
may be flaky, and which would make a red CI run unexplainable.

## Proposal

A `tests/conftest.py` that registers and loads a hypothesis profile with `derandomize=True`
and no example database, so every run explores the same examples. A separate opt-in profile
(`HYPOTHESIS_PROFILE=explore`) keeps random exploration available on demand.

## Acceptance criteria

- [ ] Two consecutive runs of the full suite draw identical examples (shown by a test or by
      hypothesis statistics)
- [ ] `HYPOTHESIS_PROFILE=explore scripts/task test` explores randomly
- [ ] CONTRIBUTING.md says how to explore and what to do when exploration finds a failure
