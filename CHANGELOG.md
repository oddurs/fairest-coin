# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-01

The real coin: every qubit of an IBM quantum computer flipped at once, each one predicted
first, and the prediction failed in an instructive way.

### Added

- `coin run chip-map --backend NAME --shots N (--dry-run | --submit)`: predicts every
  qubit's coin from the backend's current calibration, writes the prediction down, then
  flips all of them in one job and archives the run. Needs the `ibm` extra and
  `QISKIT_IBM_TOKEN` and `QISKIT_IBM_INSTANCE`; spends QPU time only with `--submit`.
- `coin predict --calibration PATH [--measurement-decay]`: every qubit's predicted
  P(tails) from a calibration snapshot, with unusable qubits listed and the reason given.
- `coin compare RUN`: an archived chip map against its own prediction.
- `coin.sim`: density-matrix simulation with Kraus channels applied after each gate.
- `coin.noise`: amplitude and phase damping, thermal relaxation, depolarizing, readout
  error, a calibration model that refuses incomplete or unphysical qubits, and
  `coherent_bias_bound`, the most a coherent gate error of a given size can bias the coin.
- `coin.compile`: single-qubit gates lowered to IBM's native rz, sx and x, and OpenQASM 3.
- `coin.ibm`: the one module that imports Qiskit; it submits exactly the circuit it was
  given and refuses a job whose circuit was changed on the way.
- `coin.archive` and `data/runs/`: every hardware run is kept whole and immutable, with
  its calibration, its prediction (timestamped before submission) and every shot.
- The first two hardware runs: one qubit, 4,096 shots; and all 156 qubits of
  `ibm_marrakesh`, 100,000 shots each.
- Figures rendered byte-for-byte from the archive, checked in CI: the first coin, the chip
  map, and predicted against measured bias.
- Chapter 2, "Predict the real coin".

## [0.1.0] - 2026-11-01

The ideal coin: a quantum coin built from scratch, flipped on a simulator.

### Added

- `coin flip --sim` flips the coin (H on |0⟩, then measure) on the built-in simulator;
  `--shots N` prints counts and `--seed S` replays a run.
- `coin.circuit`: circuits as immutable values of gates and measurements.
- `coin.gates`: exact gate unitaries in Qiskit's conventions, little-endian.
- `coin.sim`: statevector simulation by tensor contraction, exact Born probabilities, and
  shots sampled from a caller-supplied seeded generator.
- Chapter 0, "Your coin is unfair", and chapter 1, "The ideal coin".
- A test suite that runs every example, code excerpt and command quoted in the chapters
  and the README.

[Unreleased]: https://github.com/oddurs/fairest-coin/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/oddurs/fairest-coin/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/oddurs/fairest-coin/releases/tag/v0.1.0
