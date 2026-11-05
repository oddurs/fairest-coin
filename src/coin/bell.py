"""Two coins that always agree: the Bell pair on hardware, read in the coin's own basis.

H on one qubit, then CX onto the other, leaves (|00⟩ + |11⟩)/√2. Read both in Z and each
coin is fair on its own, yet the two always land the same way. That is the phenomenon the
CHSH test (chapter 5) turns into a proof; here it is only shown, and predicted first.

The pair is the one `chsh.rank_pairs` scores best, unless one is named; the prediction uses
the same noise model, so the agreement rate this run measures also tests that model.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from coin import chsh
from coin.archive import Prediction, Run
from coin.chipmap import MAX_SHOTS, estimate_qpu_seconds, tails_by_qubit
from coin.circuit import Circuit, Gate
from coin.compile import lower
from coin.hardware import Submission
from coin.noise import Readout, model_from_calibration, pair_gates

PURPOSE = "bell"
# A measured rate within this many standard deviations of its prediction counts as a hit.
SIGMAS = 3

CIRCUIT = Circuit(2).h(0).cx(0, 1).measure(0, 0).measure(1, 1)


@dataclass(frozen=True)
class BellPlan:
    submission: Submission
    pair: tuple[int, int]
    agreement: float  # predicted P(both bits equal)
    p_one: tuple[float, float]  # predicted P(read 1) for each qubit of the pair
    s: float  # the CHSH value predicted for this pair, which is why it was chosen
    readout_source: tuple[str, str]


def plan(
    backend: str,
    calibration: dict[str, Any],
    shots: int,
    *,
    pair: tuple[int, int] | None = None,
    measured: Mapping[int, Readout] | None = None,
) -> BellPlan:
    """The best pair (or `pair`), its predicted agreement and marginals, and the job."""
    if not 1 <= shots <= MAX_SHOTS:
        raise ValueError(f"shots must be between 1 and {MAX_SHOTS:,}, got {shots}")
    ranked = {score.pair: score for score in chsh.rank_pairs(calibration, measured)}
    if not ranked:
        raise ValueError("no coupled pair in this calibration has usable noise data")
    if pair is None:
        key = min(ranked, key=lambda p: (-ranked[p].s, p))
    else:
        key = (min(pair), max(pair))
        if key not in ranked:
            raise ValueError(
                f"qubits {key[0]} and {key[1]} are not a coupled pair with usable calibration"
            )
    chosen = ranked[key]
    a, b = chosen.pair
    model = model_from_calibration(calibration)
    readout = tuple((measured or {}).get(q, model.qubits[q].readout) for q in (a, b))
    distribution = chsh.predict_distribution(
        model.qubits[a],
        model.qubits[b],
        pair_gates(calibration)[a, b],
        (readout[0], readout[1]),
        CIRCUIT,
    )
    # Outcome strings are "<b's bit><a's bit>".
    agreement = distribution.get("00", 0.0) + distribution.get("11", 0.0)
    p_one = (
        distribution.get("01", 0.0) + distribution.get("11", 0.0),
        distribution.get("10", 0.0) + distribution.get("11", 0.0),
    )
    values = {
        "purpose": PURPOSE,
        "model": "relaxation and depolarizing per gate, cz included, then readout",
        "pair": [a, b],
        "agreement": agreement,
        "p_one": {str(a): p_one[0], str(b): p_one[1]},
        "readout_source": {str(a): chosen.readout_source[0], str(b): chosen.readout_source[1]},
        "predicted_s": chosen.s,
        "shots": shots,
    }
    submission = Submission(
        circuit=lower(CIRCUIT),
        backend=backend,
        layout=(a, b),
        shots=shots,
        calibration=calibration,
        prediction=Prediction(written_at=datetime.now(UTC), values=values),
    )
    return BellPlan(submission, (a, b), agreement, p_one, chosen.s, chosen.readout_source)


def summary(chosen: BellPlan) -> str:
    a, b = chosen.pair
    gates = " ".join(
        f"{op.name}{list(op.qubits)}"
        for op in chosen.submission.circuit.ops
        if isinstance(op, Gate)
    )
    return "\n".join(
        [
            f"backend      {chosen.submission.backend}",
            f"pair         {a}-{b}, the coupled pair with the best predicted CHSH value "
            f"(S = {chosen.s:.3f})",
            f"readout      {chosen.readout_source[0]} for {a}, {chosen.readout_source[1]} for {b}",
            f"circuit      {gates}, then measure both",
            f"shots        {chosen.submission.shots:,}",
            f"predicted    agreement {chosen.agreement:.2%}; P(1) {chosen.p_one[0]:.2%} on {a}, "
            f"{chosen.p_one[1]:.2%} on {b}",
            f"estimated    ~{estimate_qpu_seconds(chosen.submission.shots):.0f} QPU seconds",
        ]
    )


def report(run: Run) -> str:
    """How often the two coins agreed, and how each leaned, against what was predicted."""
    values = run.prediction.values if run.prediction else {}
    if values.get("purpose") != PURPOSE:
        raise ValueError(f"job {run.job_id}: not a Bell run")
    n = run.shots
    agreed = sum(k for outcome, k in run.counts.items() if outcome[0] == outcome[1])
    tails = tails_by_qubit(run)
    lines = [f"pair         {run.qubits[0]}-{run.qubits[1]}, {n:,} shots"]
    lines.append(_line("agreement", agreed / n, values["agreement"], n))
    for q in run.qubits:
        lines.append(_line(f"P(1) on {q}", tails[q] / n, values["p_one"][str(q)], n))
    return "\n".join(lines)


def _line(name: str, measured: float, predicted: float, n: int) -> str:
    sigma = math.sqrt(predicted * (1 - predicted) / n)
    if sigma == 0:  # a certain prediction: any departure is infinitely unlikely
        z = 0.0 if measured == predicted else math.inf
    else:
        z = (measured - predicted) / sigma
    verdict = "within" if abs(z) <= SIGMAS else "outside"
    return (
        f"{name:<12} {measured:.2%} measured, {predicted:.2%} predicted, z = {z:+.1f} "
        f"({verdict} {SIGMAS}σ)"  # noqa: RUF001 - σ is the display text
    )
