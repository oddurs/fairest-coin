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

import numpy as np

from coin.archive import Prediction, Run
from coin.circuit import Circuit, Gate, Measure
from coin.hardware import Submission
from coin.noise import coherent_bias_bound, model_from_calibration, predict_tails

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


@dataclass(frozen=True)
class QubitResult:
    """One qubit of an archived chip map: what was predicted, and what it did."""

    qubit: int
    predicted: float
    alternative: float | None  # None where the calibration had no readout length
    measured: float
    shots: int

    @property
    def sigma(self) -> float:
        """The spread of the measured fraction if the prediction were exactly right."""
        return math.sqrt(self.predicted * (1 - self.predicted) / self.shots)

    @property
    def z(self) -> float:
        """How many σ the measurement landed from the prediction."""
        return (self.measured - self.predicted) / self.sigma


def within_three_sigma(measured: float, predicted: float, shots: int) -> bool:
    """Whether a measured fraction is within 3σ of a predicted probability over `shots`.

    σ is the prediction's own binomial spread, so a prediction of exactly 0 or 1 claims that
    nothing else can happen, and any other outcome misses it.
    """
    return abs(measured - predicted) <= 3 * math.sqrt(predicted * (1 - predicted) / shots)


def compare(run: Run) -> list[QubitResult]:
    """Every predicted qubit of an archived chip map against what it measured, by qubit."""
    # A single-qubit run's p_tails is one number; a chip map's is one per qubit.
    if run.prediction is None or not isinstance(run.prediction.values.get("p_tails"), dict):
        raise ValueError(f"job {run.job_id}: not a chip map; it has no p_tails per qubit")
    values = run.prediction.values
    alternative = values.get("p_tails_measurement_decay", {})
    tails = tails_by_qubit(run)
    return [
        QubitResult(
            qubit=int(q),
            predicted=p,
            alternative=alternative.get(q),
            measured=tails[int(q)] / run.shots,
            shots=run.shots,
        )
        for q, p in sorted(values["p_tails"].items(), key=lambda item: int(item[0]))
    ]


def report(run: Run) -> str:
    """An archived chip map against its prediction, in the numbers chapter 2 quotes."""
    results = compare(run)
    assert run.prediction is not None  # compare() refuses a run without one
    values = run.prediction.values
    lead = (run.submitted_at - run.prediction.written_at).total_seconds()
    measured = [r.measured - 0.5 for r in results]
    both = [r for r in results if r.alternative is not None]

    def within_3_sigma(predicted: list[float], rows: list[QubitResult]) -> int:
        return sum(
            within_three_sigma(r.measured, p, r.shots) for r, p in zip(rows, predicted, strict=True)
        )

    model_p = [r.predicted for r in results]
    alternative_p = [r.alternative for r in both if r.alternative is not None]
    closer = sum(
        abs(r.measured - r.predicted) < abs(r.measured - a)
        for r, a in zip(both, alternative_p, strict=True)
    )
    calibrated = model_from_calibration(run.calibration).qubits
    if missing := sorted(r.qubit for r in results if r.qubit not in calibrated):
        raise ValueError(f"job {run.job_id}: predicted qubits {missing} have no usable calibration")
    bounds = {r.qubit: coherent_bias_bound(calibrated[r.qubit].gates["sx"].error) for r in results}

    def coherent_reach(q: int) -> float:
        # The bound limits the qubit's true P(tails); readout shrinks any change in it by the
        # contrast 1 − p(1|0) − p(0|1) before it reaches the measured fraction.
        readout = calibrated[q].readout
        return bounds[q] * (1 - readout.p1_given_0 - readout.p0_given_1)

    explained = sum(
        abs(r.measured - r.predicted) <= coherent_reach(r.qubit) + 3 * r.sigma for r in results
    )

    def pct(x: float) -> str:
        return f"{x:+.2%}"

    def correlation(xs: list[float], ys: list[float]) -> str:
        # Undefined for fewer than two values or for values that never vary.
        try:
            return f"{statistics.correlation(xs, ys):+.2f}"
        except statistics.StatisticsError:
            return "—"

    # A calibration without readout lengths gives no alternative prediction; the run is still
    # worth reporting against the model.
    if both:
        alt_within = str(within_3_sigma(alternative_p, both))
        alt_median = pct(statistics.median(p - 0.5 for p in alternative_p))
        alt_correlation = correlation(alternative_p, [r.measured - 0.5 for r in both])
        alt_closer = str(len(both) - closer)
        closer_text = str(closer)
    else:
        alt_within = alt_median = alt_correlation = alt_closer = closer_text = "—"

    rows = [
        f"run          {run.backend}, job {run.job_id}, "
        f"{len(run.qubits)} qubits × {run.shots:,} shots",  # noqa: RUF001 - × is the display text
        f"prediction   written {lead:.1f} s before submission; "
        f"{len(results)} qubits predicted, {len(values.get('excluded', {}))} excluded",
        f"{'':29}{'model':>7}{'alternative':>14}",
        f"{'within 3σ':29}{within_3_sigma(model_p, results):>7}"  # noqa: RUF001 - σ is the display text
        f"{alt_within:>14}",
        f"{'median bias, predicted':29}{pct(statistics.median(p - 0.5 for p in model_p)):>7}"
        f"{alt_median:>14}",
        f"{'median bias, measured':29}{pct(statistics.median(measured)):>7}",
        f"{'correlation with measured':29}{correlation(model_p, measured):>7}{alt_correlation:>14}",
        f"{'closer to the measurement':29}{closer_text:>7}{alt_closer:>14}",
        f"coherent     {explained} of {len(results)} within 3σ if each sx error may be "  # noqa: RUF001 - σ is the display text
        f"coherent (median bound ±{statistics.median(bounds.values()):.2%})",
    ]
    if not both:
        rows.append("alternative  not predicted: the calibration gave no readout lengths")
    if run.memory is not None:
        z = _drift(run)
        moved = sum(abs(v) > 3 for v in z.values())
        # Coins that held still would pass 3σ by chance with probability erfc(3/√2) each.
        expected = len(z) * math.erfc(3 / math.sqrt(2))
        rows.append(
            f"drift        {moved} of {len(z)} qubits changed by more than 3σ between the run's "  # noqa: RUF001 - σ is the display text
            f"halves ({expected:.1f} expected if they held still)"
        )
    rows.append(f"{'largest misses':17}{'predicted':>12}{'measured':>12}{'off by':>10}")
    for r in sorted(results, key=lambda r: -abs(r.z))[:5]:
        rows.append(
            f"{r.qubit:>5}{'':12}{pct(r.predicted - 0.5):>12}{pct(r.measured - 0.5):>12}"
            f"{f'{r.z:+.1f}σ':>10}"  # noqa: RUF001 - σ is the display text
        )
    return "\n".join(rows)


def _drift(run: Run) -> dict[int, float]:
    """Each measured qubit's change in P(tails) between the two halves of a run, in σ.

    A qubit whose P(tails) held still for the whole job gives a standard normal z, so about
    0.27% of steady qubits land beyond 3σ. Qubits that never or always came up tails carry
    no information about change and are left out.
    """
    assert run.memory is not None
    width = len(run.memory[0])
    bits = np.frombuffer("".join(run.memory).encode(), dtype=np.uint8).reshape(-1, width)
    tails = (bits == ord("1"))[:, ::-1]  # column i is classical bit i, the rightmost first
    half = len(tails) // 2
    first, second = tails[:half].mean(axis=0), tails[half:].mean(axis=0)
    pooled = tails.mean(axis=0)
    scale = 1 / half + 1 / (len(tails) - half)
    return {
        run.qubits[clbit]: float((second[clbit] - first[clbit]) / math.sqrt(p * (1 - p) * scale))
        for clbit, p in enumerate(pooled)
        if 0 < p < 1
    }


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
