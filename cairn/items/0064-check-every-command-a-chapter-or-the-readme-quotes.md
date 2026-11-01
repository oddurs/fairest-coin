---
id: 64
uid: bf68f698-0753-4c72-9c7b-ebce2a0a76e6
title: Check every command a chapter or the README quotes
type: bug
status: backlog
milestone: v0.2
created: 2026-11-01
updated: 2026-11-01
priority: p1
effort: s
area: essay
---

## What happens

`tests/test_chapters.py` treats only the first line of a console block as a command and
does not handle `SystemExit`, so a block with two commands, or one quoting `coin --version`,
fails confusingly. The README's quickstart `coin flip --sim` sits in an `sh` block the
checker never runs, although the README says every command is checked.

## What should happen

Each `$ coin …` line in a console block is run, with the lines up to the next `$` as its
expected output; `--version` and `--help` work; the README's quickstart flip is checked.

## Reproduction

1. Add a console block with `$ coin --version` to a chapter: the test errors with SystemExit.

Found by the v0.1 milestone review; defect in 0012 and 0013.
