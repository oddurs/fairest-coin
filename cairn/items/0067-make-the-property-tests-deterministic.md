---
id: 67
uid: 888da86a-1387-487c-bd46-9c50f226690a
title: Make the property tests deterministic
type: chore
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
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

- [x] Two consecutive runs of the full suite draw identical examples (shown by a test or by
      hypothesis statistics)
- [x] `HYPOTHESIS_PROFILE=explore scripts/task test` explores randomly
- [x] CONTRIBUTING.md says how to explore and what to do when exploration finds a failure

## Result

tests/conftest.py loads a derandomized hypothesis profile with no example database by default; HYPOTHESIS_PROFILE=explore searches randomly with 1,000 examples. tests/test_determinism.py proves two runs draw identical examples (and explore runs differ, checked by hand). CONTRIBUTING.md explains exploring and turning a found failure into a fixed case.

## 2026-11-01

Root cause found while building 0068: the unexplained failure is hypothesis's 200 ms deadline. Qiskit's first qasm3.loads costs 50-100 ms cold (measured) and under 1 ms warm, so under load the first example of test_qasm_parses_in_qiskit_to_the_same_unitary can exceed the deadline once and pass on replay, which is why the saved example never reproduced. Both profiles now set deadline=None, pinned by a test.
