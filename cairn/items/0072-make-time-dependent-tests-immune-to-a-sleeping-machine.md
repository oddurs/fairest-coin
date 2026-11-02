---
id: 72
uid: e90668f0-4a22-46b1-8268-0279f932687c
title: Make time-dependent tests immune to a sleeping machine
type: bug
status: done
milestone: v0.3
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p1
effort: s
area: tooling
---

## What happens

## What should happen

## Reproduction

1.
## Problem

`tests/test_hardware.py` builds one parametrized case with a prediction timestamped
`datetime.now(UTC) + timedelta(hours=1)`. That is evaluated when pytest collects the tests,
not when the case runs. If the machine sleeps for more than an hour in between, the
"future" timestamp is in the past, the submission is no longer refused, and the test fails.
It failed this way once, in a full check on 2026-11-02.

Around the same time, a full suite ran for over 40 minutes at 99% CPU, and another check
overran 600 s. A rerun with `faulthandler_timeout` passed in 65 s, so the cause is
unconfirmed. A sleeping machine would explain the overruns; nothing would explain a
genuine spin.

## Proposal

- Compute time-relative parameters inside the test, not at collection.
- Set `faulthandler_timeout` in the pytest configuration, so any test that runs long dumps
  every thread's stack instead of hanging silently, locally and in CI.

## Acceptance criteria

- [x] No parametrized test case computes a timestamp at collection time
- [x] Parametrized cases are factories, called when the test runs, so a sleep between collection and run cannot stale them
- [x] pytest dumps tracebacks for any test running longer than the configured timeout

## 2026-11-02

Evidence: grep finds no datetime.now/time.time inside any parametrize list; test_hardware's cases are lambdas called inside the test. pyproject sets faulthandler_timeout = 300; tests/test_harness.py asserts the setting and shows the mechanism on a subprocess pytest run (a 3 s test under a 1 s timeout prints 'Timeout' and names the test). The 40-minute spin was not reproduced (rerun passed in 65 s); with the timeout in place, a recurrence will leave a stack.

## Result

test_hardware's parametrized cases are factories; pytest's faulthandler_timeout = 300 dumps the stack of any test that runs that long.
