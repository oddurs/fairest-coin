# The Fairest Coin

[![CI](https://github.com/oddurs/fairest-coin/actions/workflows/ci.yml/badge.svg)](https://github.com/oddurs/fairest-coin/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Can you prove a coin flip is random?**

A tossed coin is deterministic physics: it lands on the side it started on slightly more
often than half the time. A pseudo-random generator is deterministic by design. Statistical
tests can only fail to find a pattern; they can never prove there isn't one. Quantum
mechanics is the one place where randomness can come with a proof, and the proof needs
entanglement.

This project builds a quantum coin from nothing, with its own simulator, noise model and
compiler, and runs it on real IBM quantum hardware, asking the same question more
rigorously in each chapter. Each chapter predicts before it measures. The
last one ends with a coin whose every flip carries a receipt: the job, the qubit, and the
Bell-inequality violation that certifies it.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/oddurs/fairest-coin
```

To run on IBM hardware too, install the `ibm` extra, which brings in Qiskit:

```sh
uv tool install "fairest-coin[ibm] @ git+https://github.com/oddurs/fairest-coin"
```

Flip the coin once, then ten thousand times. `--seed` makes a run replayable; leave it off
for a fresh flip.

```console
$ coin flip --sim --seed 1
HEADS
$ coin flip --sim --shots 10000 --seed 1
heads   4,971   49.71%
tails   5,029   50.29%
```

`coin flip` runs on a simulator written from scratch in `src/coin/`, so its flips come
from a seeded pseudo-random generator. [Chapter 1](docs/chapters/01-the-ideal-coin.md)
explains why that is not good enough.

On real hardware, `coin run chip-map` predicts every qubit of an IBM backend from its
calibration, then flips them all in one job (it needs an IBM Quantum account, and spends
QPU time only with `--submit`). `coin compare` holds an archived run in `data/runs/`
against its prediction. [Chapter 2](docs/chapters/02-predict-the-real-coin.md) is what
happened the first time.

## The chapters

| Chapter | Question | Status |
|---|---|---|
| [0. Your coin is unfair](docs/chapters/00-your-coin-is-unfair.md) | Why does this question matter? | written |
| [1. The ideal coin](docs/chapters/01-the-ideal-coin.md) | What is a quantum coin? | written |
| [2. Predict the real coin](docs/chapters/02-predict-the-real-coin.md) | How does real hardware bend it? | written |
| 3. Make it fair | Can a biased coin be fixed? | upcoming in v0.3 |
| 4. Two coins that agree | What is entanglement for? | upcoming in v0.4 |
| 5. The proof | Can randomness be certified? | upcoming in v0.4 |
| Epilogue | What would it really take? | upcoming in v1.0 |

Every example, code excerpt and command in the chapters is run by the test suite, so the
essay cannot drift from the code. The plan, milestone by milestone, is in
[ROADMAP.md](ROADMAP.md).

## Development

```sh
git clone git@github.com:oddurs/fairest-coin.git
cd fairest-coin
scripts/setup          # wires the git hooks and syncs the environment, once
scripts/agent doctor   # verifies the toolchain
```

Every change happens in its own worktree and branch and lands through a pull request:

```sh
scripts/agent start feat/statevector-simulator   # prints the worktree path
scripts/agent commit "feat(sim): simulate circuits as statevectors"
scripts/agent pr
```

`scripts/task check` runs formatting, lint, type checks, tests and the build — the same
command CI runs. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

[MIT](LICENSE) © 2026 Oddur Sigurdsson
