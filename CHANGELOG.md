# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-11-02

Hardening: every defect a review of the first three milestones found, fixed with the test
that would have caught it, and a v0.4 plan rebuilt on what the hardware showed.

### Added

- `coin recover [JOB_ID] [--record FILE] [--force]` archives a submitted job whose
  process died or whose archive failed, from the pending record `submit` now writes
  before it submits. `coin recover --discard FILE` removes a record that never reached
  IBM. A job is never archived twice or under the wrong id.
- `coin publish RUN` writes a spent harvest's extraction record into its archived run.
- `coin harvest` forecasts its yield from simulated coins at the predicted bias and
  refuses a run that would give fewer than 1,000 bits, before it submits.
- `noise.average_infidelity` and `noise.gate_depolarizing`.

### Changed

- The essay and README say what the data now shows: chapter 3 opens on rank and robust
  statistics, chapter 2 tells what spike 0069 found, and nothing promises loophole-free
  certification.
- The v0.4 plan claims no randomness expansion, bounds S with Hoeffding at a stated ε,
  hashes certified bits at the certified rate, and names what it still assumes.
- Commit subjects are capped at 64 characters, so the squash merge stays within 72.

### Fixed

- A job submitted to IBM could be lost, with its shots and prediction, if the process
  died or archiving failed after submission. QPU seconds now come from IBM's charge.
- The IBM adapter scrubbed the token only verbatim; percent- and form-encoded copies now
  go too. Its circuit-change check now compares classical bits.
- `min_entropy` could score a short repeated block as random. Each guesser is now scored
  only on at least 100 of its own guesses.
- The pool could take one job twice, or a run that was not a harvest or was already
  published.
- `coin compare` failed on a chip map whose calibration had no readout length.
- The noise model counted gate relaxation twice (an effect on the coin under 1.3e-5).
- Four places where a mutant of the code survived the tests.
- The pre-push hook misread whether runs were tracked when git set `GIT_DIR`.

## [0.3.0] - 2026-11-02

The fair coin: real hardware flips, made fair without knowing their bias, spent one at a
time with a receipt, and an honest account of what no test can prove.

### Added

- `coin harvest --backend NAME --shots N (--dry-run | --submit | --from-run DIR)` runs
  the coin on the qubit whose readout errs least and archives the raw run. It then
  extracts near-uniform bits with Toeplitz hashing and adds them to a local entropy pool.
- `coin pool` shows each batch in the pool and how much of it is spent.
- `coin flip` without `--sim` spends one pool bit, never twice, even across processes.
  It prints a receipt (backend, qubit, job, run, extraction). `--json` emits the receipt
  per `docs/receipt.schema.json`, and `--quiet` prints only the face.
- `coin run readout --prepare {0,1}` prepares |0⟩ or |1⟩ on every qubit and measures,
  testing the backend's published readout directly.
- `coin.extract`:
  - `von_neumann` and `peres`;
  - `min_entropy`, a conservative estimate that does not assume independence, built from
    bias, worst-block, Markov, lag, online-Markov and phase guessers;
  - `toeplitz` and `toeplitz_extract`, which spend half the estimate.
- `coin.battery`: monobit, block frequency, runs, longest run and serial tests from NIST
  SP 800-22, reproducing its worked examples. Also `pi_bits`, which passes all of them.
- `coin.mitigate`: readout correction of estimated distributions (not bits).
- `coin.pool`: the on-disk pool, with locking and durable, atomic writes.
- Spikes 0028 (are the hardware bits independent?) and 0069 (why did the chip-map
  prediction miss?), with their analysis scripts and runs.
- Four new hardware runs: two readout jobs, a second chip map, and a 100,000-shot harvest.
  The harvest was committed with its extraction record after its batch was spent.
- The before-and-after extraction figure.
- Chapter 3, "Make it fair".

### Changed

- `coin flip` without `--sim` now spends a bit from the entropy pool (and exits 1 with
  "run `coin harvest`" when it is empty); in 0.2.0 it exited 2 and pointed to `--sim`.

### Fixed

- `chipmap.compare` refused a single-qubit run only by crashing.
- Time-relative test cases were built at collection, so a sleeping machine could stale
  them. Tests that run five minutes now dump their stack.
- `coin pool`'s table did not line up with real batch names.

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

[Unreleased]: https://github.com/oddurs/fairest-coin/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/oddurs/fairest-coin/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/oddurs/fairest-coin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/oddurs/fairest-coin/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/oddurs/fairest-coin/releases/tag/v0.1.0
