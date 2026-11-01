# The Fairest Coin

[![CI](https://github.com/oddurs/fairest-coin/actions/workflows/ci.yml/badge.svg)](https://github.com/oddurs/fairest-coin/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Can you prove a coin flip is random?**

A tossed coin is deterministic physics: it lands on the side it started on slightly more
often than half the time. A pseudo-random generator is deterministic by design. Statistical
tests can only fail to find a pattern; they can never prove there isn't one. Quantum
mechanics is the one place where randomness comes with a proof, and the proof needs
entanglement.

This project builds a quantum coin from nothing — its own simulator, noise model and
compiler — and runs it on real IBM quantum hardware, asking the same question more
rigorously in each chapter. Every chapter predicts before it measures, every hardware run
is archived with the calibration data of that day, and the final coin hands out bits with
a receipt: the job, the qubit, and the Bell-inequality violation that certifies them.

## Status

The project has just started. Today `coin` is an installable command with no experiments
yet. The plan, milestone by milestone, is in [ROADMAP.md](ROADMAP.md).

| Chapter | Question | Status |
|---|---|---|
| [0. Your coin is unfair](docs/chapters/00-your-coin-is-unfair.md) | Why does this question matter? | written |
| 1. The ideal coin | What is a quantum coin? | upcoming in v0.1 |
| 2. Predict the real coin | How does real hardware bend it? | upcoming in v0.2 |
| 3. Make it fair | Can a biased coin be fixed? | upcoming in v0.3 |
| 4. Two coins that agree | What is entanglement for? | upcoming in v0.4 |
| 5. The proof | Can randomness be certified? | upcoming in v0.4 |
| Epilogue | What would it really take? | upcoming in v1.0 |

## Install

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/oddurs/fairest-coin
coin --version
```

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
