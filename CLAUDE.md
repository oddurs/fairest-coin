# fairest-coin

An educational quantum project: a coin built from scratch (simulator, noise model,
compiler) and run on real IBM hardware, asking whether a coin flip can be proven random.
The library is `src/coin/`, the essay is `docs/chapters/`, archived hardware runs are
`data/runs/`, the plan is `cairn/items/`.

## Rules

- **Never name a model, an assistant, or an AI tool in anything that reaches git or
  GitHub.** No co-author trailers, no "generated with" footers, no robot emoji. The work
  is published under the owner's name. `scripts/attribution` checks commit messages and
  PR bodies; do not route around it.
- **Never commit on `main`.** One unit of work → `scripts/agent start <type>/<slug>` →
  one worktree in `../.worktrees/<repo>/<type>/<slug>/` → one PR. Parallel agents never
  share a checkout.
- **Green before a PR.** `scripts/task check` must pass. Never `--no-verify`, never
  `|| true`.
- **Never spend QPU time without being asked.** The free allowance is minutes per month.
  Anything that submits to IBM needs the owner's explicit go-ahead for that run.
- **Never commit an API key.** It lives in `QISKIT_IBM_TOKEN`, in the environment only.

## The seam

All automation goes through `scripts/task`; never call ruff, ty or pytest directly in CI
or hooks.

```sh
scripts/task fmt        # format and autofix
scripts/task fmt:check  # formatting drift fails
scripts/task lint       # ruff + ty, warnings are errors
scripts/task test       # pytest
scripts/task build      # builds the wheel
scripts/task check      # all of the above, what CI runs
```

## The workflow

```sh
scripts/agent doctor                       # verify the environment
scripts/agent start feat/0009-statevector   # prints the worktree path; cd there yourself
scripts/agent commit "feat(sim): simulate circuits as statevectors"
scripts/agent pr --body-file /path/to/body.md
scripts/agent done                         # after the squash merge
```

Branch types: `feat fix chore docs perf refactor test`; the slug starts with the cairn id.
Commits are Conventional Commits, subject ≤ 72 characters, no trailing period, body says
why, `Refs: 0009` trailer. A PR body states the problem, the approach, and what a reviewer
should look at sceptically — say where it is weak.

## Python

uv for everything, ruff for lint and format, ty for types, pytest with plain asserts.
Annotate every public signature. numpy is the only runtime dependency until Qiskit
arrives, and Qiskit is only ever imported in `src/coin/ibm.py`. Physics conventions are in
`.claude/rules/physics.md`.

A bug fix arrives with the test that would have caught it. Comments say why.

<!-- cairn:begin -->
## Roadmap and issues

This project tracks its roadmap and issues with `cairn`. Every item is a Markdown file under `cairn/items`, described by the schema in `cairn.toml`.

**Do not create ad-hoc TODO, PLAN or NOTES files.** Create a cairn item instead, so the work appears on the board and in the generated roadmap.

### The loop

1. `cairn next` — what is ready to start. It excludes anything blocked by unfinished dependencies and puts work already in progress first.
2. `cairn claim <ID>` — take it before you start, so no one duplicates the work. `cairn claim --next` picks and claims the top-ranked unclaimed item in one step. Then read `cairn prompt <ID>`: the item with everything it rests on — the outcome it serves, what its dependencies concluded, what done means and what earlier runs learned.
3. Do the work. Record what you learn: `cairn set <ID> <field>=<value>` for fields, `cairn note <ID> "<TEXT>"` for anything that needs a sentence — why you chose something, what you tried, what to watch for.
4. `cairn tick <ID> <N>` as each acceptance criterion becomes true — `cairn show <ID> --criteria` lists them numbered. Tick what is true, not what would let you close.
5. `cairn close <ID>` when it is done, or `cairn release <ID>` to hand it back.
6. `cairn check` before you report finished. It must pass.

### Commands

```sh
cairn next --json                 # ready work, ranked
cairn claim --next                # take the next ready item
cairn search <TEXT> --json        # titles, bodies and labels
cairn list --json                 # all open items
cairn list --filter 'blocked=false,priority=p0'
cairn prompt <ID>                 # the item as a prompt, with what it rests on
cairn show <ID> --json            # one item, including its body
cairn new "<TITLE>" --type <TYPE> --milestone <MILESTONE>
cairn set <ID> status=<STATUS>    # also labels+=x, or any field below
cairn note <ID> "<TEXT>"          # append reasoning; never replaces
cairn show <ID> --criteria        # acceptance criteria, numbered
cairn tick <ID> <N>               # tick one; --all for every one
cairn close <ID>
cairn check                       # validate; run before finishing
cairn render                      # regenerate ROADMAP.md
```

Claims coordinate writers in the same item directory and are seen across the worktrees of this repository: `next` leaves out what another worktree has claimed, `claim` refuses it, and `cairn worktrees` shows what each is doing. Separate clones are not read. Agree on assignments before splitting work across clones.

Items are numbered: `0012`, and commands accept the bare number too. Write the number in `depends_on` and other id references. Each item also carries a `uid` tag; leave it alone. If a merge gives two items one number, `cairn renumber` moves the one that arrived and retargets the references that came with it.

### Schema

- **Types**: `feature`, `bug`, `chore`, `docs`, `spike`, `milestone`
- **Statuses**: `backlog` (open), `planned` (open), `doing` (active), `blocked` (active), `done` (done), `dropped` (dropped)
- **`due`**: date, YYYY-MM-DD — when a milestone is meant to land
- **`part_of`**: names any items, by id, several allowed — a larger piece of work this belongs to
- **`priority`**: one of p0, p1, p2, p3 — p0 is a release blocker
- **`effort`**: one of s, m, l, xl — Rough size, not an estimate
- **`area`**: one of sim, noise, compile, hardware, extract, chsh, cli, essay, figures, tooling — Subsystem this touches
- **`qpu`**: true or false — spends real hardware time from the free monthly allowance
- **Milestones**: `v0.1` (due 2026-11-08), `v0.2` (due 2026-11-22), `v0.3` (due 2026-12-06), `v0.4` (due 2026-12-27), `v1.0` (due 2027-01-17), `later`
- **Saved views** (`cairn list --view NAME`): `now`, `next`, `triage`

### Rules

1. Before starting work, find or create the item and set it to an active status.
2. Use the fields above rather than inventing new ones; add new fields to `cairn.toml` first.
3. Never hand-edit the generated roadmap file — change items and run `cairn render`.
4. `cairn check` must pass before the work is considered done.

<!-- cairn:end -->
