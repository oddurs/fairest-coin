"""The chip map: every qubit of a backend is a coin, all flipped in one job.

A backend with 156 qubits is 156 different coins. One job flips them all at once (they are
measured in parallel, so it costs no more than flipping one), and every qubit's prediction is
written down before it is submitted, under two models (spike 0018): readout error with decay
during gates, which is the model, and the same plus decay over the measurement window, which
double counts and is recorded so the hardware can say which one it agrees with.
"""

import math
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from coin.archive import Prediction, Run
from coin.circuit import Circuit, Gate, Measure
from coin.hardware import Submission
from coin.noise import model_from_calibration, predict_tails

MAX_SHOTS = 100_000  # the per-job limit IBM's Heron backends report
# Spike 0015 billed 3 s for 4,096 shots: about 1 s of shots at the default 250 µs repetition
# delay, plus about 2 s per job. All qubits are measured in parallel, so width costs nothing.
_SECONDS_PER_JOB = 2.0
_SECONDS_PER_SHOT = 250e-6


@dataclass(frozen=True)
class ChipMap:
    """A planned chip map: what will run, and what each qubit is predicted to do."""

    submission: Submission
    p_tails: dict[int, float]
    p_tails_measurement_decay: dict[int, float]
    excluded: dict[int, str]

    @property
    def sigma(self) -> dict[int, float]:
        """The binomial standard error of each qubit's measured tails fraction."""
        n = self.submission.shots
        return {q: math.sqrt(p * (1 - p) / n) for q, p in self.p_tails.items()}

    @property
    def estimated_qpu_seconds(self) -> float:
        return estimate_qpu_seconds(self.submission.shots)


def estimate_qpu_seconds(shots: int) -> float:
    return _SECONDS_PER_JOB + shots * _SECONDS_PER_SHOT


def plan(backend: str, calibration: dict[str, Any], shots: int) -> ChipMap:
    """Predict every qubit from `calibration` and build the job that tests the predictions.

    The prediction is timestamped now, so plan immediately before submitting.
    """
    if not 1 <= shots <= MAX_SHOTS:
        raise ValueError(f"shots must be between 1 and {MAX_SHOTS:,}, got {shots}")
    n = len(calibration["qubits"])
    model = model_from_calibration(calibration)
    one = _native_coin(1)
    p_tails = {q: predict_tails(noise, one) for q, noise in model.qubits.items()}
    with_decay = {
        q: predict_tails(noise, one, measurement_decay=True)
        for q, noise in model.qubits.items()
        if noise.readout_length_ns is not None
    }
    prediction = Prediction(
        written_at=datetime.now(UTC),
        values={
            "model": "readout confusion + thermal relaxation and depolarizing per gate",
            "alternative": "the model + T1/T2 over the readout window (double counts readout)",
            "shots": shots,
            "p_tails": {str(q): p for q, p in sorted(p_tails.items())},
            "p_tails_measurement_decay": {str(q): p for q, p in sorted(with_decay.items())},
            "excluded": {str(q): reason for q, reason in sorted(model.excluded.items())},
        },
    )
    submission = Submission(
        circuit=_native_coin(n),
        backend=backend,
        layout=tuple(range(n)),
        shots=shots,
        calibration=calibration,
        prediction=prediction,
    )
    return ChipMap(submission, p_tails, with_decay, dict(model.excluded))


def tails_by_qubit(run: Run) -> dict[int, int]:
    """How many shots came up tails on each measured qubit of a run."""
    width = len(next(iter(run.counts)))
    tails: Counter[int] = Counter()
    for outcome, count in run.counts.items():
        for clbit, bit in enumerate(reversed(outcome)):  # classical bit 0 is rightmost
            if bit == "1":
                tails[clbit] += count
    # Classical bit i reads virtual qubit i, which the layout placed on physical qubit i.
    return {run.qubits[clbit]: tails[clbit] for clbit in range(width)}


def summary(chip: ChipMap) -> str:
    """The plan in words: what runs, what is predicted, what it costs."""
    shots = chip.submission.shots
    biases = [p - 0.5 for p in chip.p_tails.values()]
    sigma = statistics.median(chip.sigma.values())
    visible = sum(abs(p - 0.5) > 3 * chip.sigma[q] for q, p in chip.p_tails.items())
    lines = [
        f"backend      {chip.submission.backend}, {chip.submission.circuit.n_qubits} qubits",
        "circuit      rz(π/2) · sx · rz(π/2) · measure on every qubit, in parallel",
        f"shots        {shots:,} (1σ ≈ {sigma:.2%} per qubit)",  # noqa: RUF001 - σ is the display text
        f"predicted    {len(chip.p_tails)} qubits; bias median {statistics.median(biases):+.2%}, "
        f"range {min(biases):+.2%} to {max(biases):+.2%}",
        f"resolvable   {visible} qubit(s) predicted more than 3σ from fair",  # noqa: RUF001 - σ is the display text
        f"excluded     {len(chip.excluded)}: "
        + ", ".join(f"{q} ({r})" for q, r in sorted(chip.excluded.items())),
        f"estimated    ~{chip.estimated_qpu_seconds:.0f} QPU seconds",
    ]
    return "\n".join(lines)


def _native_coin(n: int) -> Circuit:
    """The coin, H lowered to rz(π/2)·sx·rz(π/2), on each of n qubits, all measured."""
    # Built in one pass: appending gate by gate re-validates the circuit each time.
    ops: list[Gate | Measure] = []
    for q in range(n):
        ops += [
            Gate("rz", (q,), (math.pi / 2,)),
            Gate("sx", (q,)),
            Gate("rz", (q,), (math.pi / 2,)),
        ]
    ops += [Measure(q, q) for q in range(n)]
    return Circuit(n, tuple(ops))
