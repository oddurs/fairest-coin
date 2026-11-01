# Contributing

## Setup, once

```sh
scripts/setup
scripts/agent doctor
```

## The workflow

One unit of work is one worktree, one branch and one pull request. `main` advances only
through a merged PR; branch protection and the `pre-push` hook both enforce it.

```sh
scripts/agent start <type>/<slug>   # new branch from origin/main in ../.worktrees/<repo>/<type>/<slug>
cd <the printed path>
# ... work ...
scripts/agent commit "<type>(<scope>): <subject>"
scripts/agent sync                  # rebase onto the latest main when needed
scripts/agent pr                    # checks, pushes, opens the PR
# after the squash merge:
scripts/agent done                  # removes the worktree and branch, fast-forwards main
```

`scripts/agent list` shows every worktree with its PR state.

Branch types: `feat fix chore docs perf refactor test`. When the work has a cairn item,
start the slug with its id: `feat/0009-statevector-simulator`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope)!: subject`,
imperative, at most 72 characters, no trailing period. The body explains why. Reference
the cairn item with a `Refs: 0009` trailer. The `commit-msg` hook enforces the format.

Pull requests are squash-merged, so the PR title becomes the commit on `main` and must
follow the same convention.

## Checks

```sh
scripts/task check   # fmt:check, lint (ruff and ty, warnings are errors), test, build
scripts/task fmt     # fix formatting and autofixable lint
```

`pre-commit` runs format and lint checks; `pre-push` runs the full `check`. CI runs the
same `scripts/task check`. Never bypass a hook with `--no-verify`.

## Figures

Every figure in `docs/figures/` is rendered from `data/runs/` by `scripts/figures`, and
`build` fails if a committed figure differs from a fresh render. To add one, write a
function from the runs directory to a matplotlib `Figure` in `src/coin/figures.py`, add it
to `FIGURES`, run `scripts/figures`, and commit the SVG it writes.

## Hardware runs

Real QPU time is scarce. Simulate first, write the prediction down before submitting, and
archive every run under `data/runs/`. An unarchived run did not happen.

## Review

This is a solo-maintained repository, so branch protection requires zero approvals: CI
green, conversations resolved and an up-to-date branch are the gates. That changes to one
required approval when a second maintainer joins.

## Planning

Work is tracked as [cairn](https://github.com/oddurs/cairn) items under `cairn/items/`;
`ROADMAP.md` is generated from them. Start with `cairn next`.
