# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-02

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

[Unreleased]: https://github.com/oddurs/fairest-coin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/oddurs/fairest-coin/releases/tag/v0.1.0
