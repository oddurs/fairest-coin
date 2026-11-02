"""Measure every qubit's readout directly: prepare |0⟩ (or |1⟩) everywhere and read it.

The chip map's coin was predicted from the backend's published readout numbers, and the
prediction missed. These runs test those numbers on their own, under the coin's own
conditions: every qubit measured at once, in the same kind of job. With one run of each
preparation, `measured` gives each qubit's readout as the job saw
it, and whatever bias the coin has left after that readout was there before measurement.
"""

import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from coin.archive import Prediction, Run
from coin.chipmap import MAX_SHOTS, tails_by_qubit
from coin.chipmap import within_three_sigma as chipmap_within
from coin.circuit import Circuit, Gate, Measure
from coin.hardware import Submission
from coin.noise import Readout


@dataclass(frozen=True)
class ReadoutPlan:
    submission: Submission
    prepare: int
    published: dict[int, float]  # p(1|0) when preparing 0, p(0|1) when preparing 1
    unpublished: dict[int, str]  # qubits with no usable readout numbers, and why

    @property
    def p_read_1(self) -> dict[int, float]:
        """The predicted chance each qubit reads 1."""
        return {q: e if self.prepare == 0 else 1 - e for q, e in self.published.items()}


_FIELD = {0: "prob_meas1_prep0", 1: "prob_meas0_prep1"}


def published_readout(
    calibration: dict[str, Any], prepare: int
) -> tuple[dict[int, float], dict[int, str]]:
    """Each qubit's published misread probability for `prepare`, straight from the snapshot.

    Not through the calibration model, which drops qubits for reasons that have nothing to do
    with readout, and drops readouts too bad to model, which are the ones worth testing.
    """
    try:
        qubits = calibration["qubits"]
        fields = [{f["name"]: f.get("value") for f in q} for q in qubits]
    except (KeyError, TypeError) as error:
        raise ValueError(f"not a calibration snapshot: {error!r}") from None
    name = _FIELD[prepare]
    published: dict[int, float] = {}
    unpublished: dict[int, str] = {}
    for q, f in enumerate(fields):
        value = f.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 1:
            unpublished[q] = f"{name} = {value!r}"
        else:
            published[q] = float(value)
    return published, unpublished


def plan(backend: str, calibration: dict[str, Any], shots: int, prepare: int) -> ReadoutPlan:
    """Prepare `prepare` on every qubit and measure; predict each from published readout."""
    if prepare not in (0, 1):
        raise ValueError(f"prepare 0 or 1, got {prepare}")
    if not 1 <= shots <= MAX_SHOTS:
        raise ValueError(f"shots must be between 1 and {MAX_SHOTS:,}, got {shots}")
    published, unpublished = published_readout(calibration, prepare)
    n = len(calibration["qubits"])
    chosen_values = {
        "model": "the backend's published readout error, nothing else",
        "purpose": "readout",
        "prepare": prepare,
        "shots": shots,
        "p_read_1": {str(q): (e if prepare == 0 else 1 - e) for q, e in sorted(published.items())},
        "unpublished": {str(q): r for q, r in sorted(unpublished.items())},
    }
    prediction = Prediction(written_at=datetime.now(UTC), values=chosen_values)
    ops: list[Gate | Measure] = [Gate("x", (q,)) for q in range(n)] if prepare else []
    ops += [Measure(q, q) for q in range(n)]
    submission = Submission(
        circuit=Circuit(n, tuple(ops)),
        backend=backend,
        layout=tuple(range(n)),
        shots=shots,
        calibration=calibration,
        prediction=prediction,
    )
    return ReadoutPlan(submission, prepare, published, unpublished)


def summary(chosen: ReadoutPlan) -> str:
    name = _FIELD[chosen.prepare].replace("prob_meas", "p(").replace("_prep", "|") + ")"
    errors = list(chosen.published.values())
    lines = [
        f"backend      {chosen.submission.backend}, {chosen.submission.circuit.n_qubits} qubits",
        f"circuit      {'x · ' if chosen.prepare else ''}measure on every qubit, "
        f"in parallel (prepare |{chosen.prepare}⟩)",
        f"shots        {chosen.submission.shots:,}",
        (
            f"predicted    {len(errors)} qubits; published {name} median "
            f"{statistics.median(errors):.2%}, max {max(errors):.2%}"
            if errors
            else "predicted    no qubit publishes a readout error"
        ),
    ]
    if chosen.unpublished:
        lines.append(
            f"unpublished  {len(chosen.unpublished)}: "
            + ", ".join(f"{q} ({r})" for q, r in sorted(chosen.unpublished.items()))
        )
    return "\n".join(lines)


def within_three_sigma(run: Run) -> tuple[int, int]:
    """How many qubits read 1 within 3σ of the published prediction, out of how many."""
    if run.prediction is None or run.prediction.values.get("purpose") != "readout":
        raise ValueError(f"job {run.job_id}: not a readout run")
    tails = tails_by_qubit(run)
    predicted = run.prediction.values["p_read_1"]
    hits = sum(
        chipmap_within(tails[int(q)] / run.shots, p, run.shots) for q, p in predicted.items()
    )
    return hits, len(predicted)


def measured(prepared_0: Run, prepared_1: Run) -> dict[int, Readout]:
    """Each qubit's readout as the two jobs saw it: p(1|0) from one, p(0|1) from the other."""
    for run, prepare in ((prepared_0, 0), (prepared_1, 1)):
        values = run.prediction.values if run.prediction else {}
        if values.get("purpose") != "readout" or values.get("prepare") != prepare:
            raise ValueError(f"job {run.job_id}: not a prepare-|{prepare}⟩ readout run")
    if prepared_0.qubits != prepared_1.qubits:
        raise ValueError("the two runs measured different qubits")
    ones_0, ones_1 = tails_by_qubit(prepared_0), tails_by_qubit(prepared_1)
    return {
        q: Readout(
            p1_given_0=ones_0[q] / prepared_0.shots,
            p0_given_1=1 - ones_1[q] / prepared_1.shots,
        )
        for q in prepared_0.qubits
    }
