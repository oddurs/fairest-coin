---
id: 65
uid: 86f8684b-aee6-446b-9a58-28c693b8e127
title: Dispatch CLI subcommands explicitly
type: chore
status: done
milestone: v0.2
assignee: Oddur Sigurdsson
created: 2026-11-01
updated: 2026-11-01
closed_at: 2026-11-01
priority: p1
effort: s
area: cli
---

## What happens

`main()` calls `_flip(args)` for any parsed command. The next subcommand (v0.2 adds
`coin predict`) would run the flip logic and fail with `AttributeError` on `args.sim`.

## What should happen

Each subparser registers its handler with `set_defaults(func=...)` and `main()` calls
`args.func(args)`. A test proves a second subcommand reaches its own handler.

## Reproduction

1. Read `src/coin/cli.py` `main`.

Found by the v0.1 milestone review; design debt in 0010.

## Result

coin.cli: each subparser registers set_defaults(handler=...) and main() returns args.handler(args). A test adds a probe subcommand and proves it reaches its own handler; it failed with AttributeError before the change.
