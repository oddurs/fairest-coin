# Physics conventions

The code, the tests and the essay all follow these.

- Follow Qiskit's conventions so hardware results need no translation: little-endian
  qubit order (qubit 0 is the rightmost bit of an outcome string), and
  RZ(θ) = diag(e^{-iθ/2}, e^{iθ/2}).
- Heads is |0⟩ and outcome `0`; tails is |1⟩ and outcome `1`. Everywhere.
- Gate equalities are tested up to global phase, unless global phase is the point.
- Every numeric tolerance is named and justified: 1e-12 for exact algebra, sampling
  error stated in σ for anything random. Never compare floats with `==`.
- Randomness in tests comes from a seeded `numpy.random.Generator`; no test may be flaky.
- A prediction is written down before the measurement it predicts. Code that submits a
  hardware run without a prediction is a bug.
- Archived runs under `data/runs/` are immutable. Fix the analysis, never the data.
