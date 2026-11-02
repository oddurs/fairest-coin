"""Harvest: one hardware job of coin flips, turned into a batch of near-uniform bits.

The coin runs on the qubit whose calibrated readout errs least, its prediction written
first like every hardware run. The raw shots are archived in `data/runs/` like any other
run. Then Toeplitz hashing (`coin.extract`) turns them into fewer, near-uniform bits, from a
fresh operating-system seed, and the batch goes into the pool with everything it rests on.

The archived shots and the batch's recorded seed determine every bit of the batch, which
makes each flip checkable afterwards and every unspent flip predictable to anyone holding
both. So a harvest run belongs in the public archive only once its batch is spent.

Spike 0028 suggested screening each batch's qubit for independence first. With Toeplitz
hashing the guarantee no longer rests on independence but on the min-entropy estimate,
whose guessers look for the same structure the screen did (memory, periods, switching), and
whose value is recorded with the batch. So there is no separate screen.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from coin.archive import EXTRACTION, Prediction, Run, add_record, load_run
from coin.circuit import Circuit
from coin.extract import (
    SAFETY,
    Bits,
    Extraction,
    min_entropy,
    secure_length,
    seed_bits,
    toeplitz_extract,
)
from coin.hardware import Submission, Transport, submit
from coin.noise import CalibrationModel, model_from_calibration, predict_tails
from coin.pool import Pool

# The coin in IBM's native gates: H = rz(π/2)·sx·rz(π/2).
NATIVE_COIN = Circuit(1).rz(math.pi / 2, 0).sx(0).rz(math.pi / 2, 0).measure(0, 0)


# A harvest is refused if it is not forecast to yield at least this many bits: near zero the
# forecast is noisy, and a few bits are not worth QPU time.
MIN_HARVEST_BITS = 1_000
# The forecast runs the estimator on this many simulated samples and takes the worst.
_FORECAST_SAMPLES = 5


@dataclass(frozen=True)
class HarvestPlan:
    submission: Submission
    qubit: int
    p_tails: float
    # The worst of several simulated runs, so a harvest the forecast allows reliably yields
    # bits. A real qubit is rarely as steady as the simulation, and may give less.
    expected_bits: int


def forecast_bits(shots: int, p_tails: float) -> int:
    """How many bits a harvest of `shots` should yield: the estimator's own verdict on a
    simulated coin at the predicted bias, at its worst over a few seeds (repeatable)."""
    worst = min(
        min_entropy((np.random.default_rng(seed).random(shots) < p_tails).astype(np.uint8))
        for seed in range(_FORECAST_SAMPLES)
    )
    return secure_length(shots, SAFETY * worst)


@dataclass(frozen=True)
class Harvest:
    run_dir: Path
    batch: str
    extraction: Extraction


def pick_qubit(model: CalibrationModel) -> int:
    """The usable qubit whose calibrated readout misreads least, both ways together."""
    if not model.qubits:
        raise ValueError("no qubit in this calibration is usable")
    return min(
        model.qubits,
        key=lambda q: (model.qubits[q].readout.p1_given_0 + model.qubits[q].readout.p0_given_1, q),
    )


def plan(backend: str, calibration: dict[str, Any], shots: int) -> HarvestPlan:
    """Choose the qubit and write the prediction. Plan immediately before submitting."""
    model = model_from_calibration(calibration)
    qubit = pick_qubit(model)
    p_tails = predict_tails(model.qubits[qubit], NATIVE_COIN)
    prediction = Prediction(
        written_at=datetime.now(UTC),
        values={
            "model": "readout confusion + thermal relaxation and depolarizing per gate",
            "purpose": "harvest",
            "qubit": qubit,
            "shots": shots,
            "p_tails": p_tails,
        },
    )
    submission = Submission(
        circuit=NATIVE_COIN,
        backend=backend,
        layout=(qubit,),
        shots=shots,
        calibration=calibration,
        prediction=prediction,
    )
    return HarvestPlan(submission, qubit, p_tails, forecast_bits(shots, p_tails))


def shots_of(run: Run) -> Bits:
    """A one-qubit run's shots as bits, in the order they ran."""
    if run.memory is None:
        raise ValueError(f"job {run.job_id} kept no per-shot memory; nothing to extract")
    if len(run.qubits) != 1:
        raise ValueError(f"job {run.job_id} measured {len(run.qubits)} qubits, not one")
    return np.frombuffer("".join(run.memory).encode(), dtype=np.uint8) - ord("0")


def harvest(
    transport: Transport, chosen: HarvestPlan, runs_dir: Path, pool: Pool, submit_script: str
) -> Harvest:
    """Run the plan, archive the raw run, extract, and add the batch to the pool.

    Everything that could stop the bits reaching the pool is checked before the job runs.
    If extraction still fails afterwards, the shots are safe in the archive and
    `extract_run` can try again.
    """
    if chosen.expected_bits < MIN_HARVEST_BITS:
        raise ValueError(
            f"{chosen.submission.shots:,} shots are forecast to yield {chosen.expected_bits:,} "
            f"bits, under the {MIN_HARVEST_BITS:,} worth a harvest; ask for more"
        )
    pool.require_writable()
    try:
        run_dir = submit(transport, chosen.submission, runs_dir, submit_script=submit_script)
    except BaseException as error:
        if getattr(error, "__notes__", None):
            error.add_note("Then `coin harvest --from-run <its run directory>` pools its bits.")
        raise
    try:
        return extract_run(run_dir, pool)
    # The QPU time is spent and the run is safe in the archive: whatever went wrong after
    # that, say so and how to finish.
    except Exception as error:
        raise HarvestError(
            f"job ran and is archived at {run_dir}, but extraction failed: {error}; "
            f"retry with `coin harvest --from-run {run_dir}`"
        ) from error


class HarvestError(RuntimeError):
    """A harvest's job ran and was archived, but its bits did not reach the pool."""


def extract_run(run_dir: Path, pool: Pool) -> Harvest:
    """Extract an archived harvest run's shots and add them to the pool as a batch.

    Only a harvest's own run qualifies, and only before it is published: once its shots and
    seed are public, every bit extracted from them is predictable. A fresh seed would hide
    that, and the bits would then owe their randomness to the seed, not the qubit the
    receipt names. Publication is recognised by the extraction record (and, in the CLI, by
    git tracking the run); a copy of public shots made elsewhere cannot be recognised.
    """
    run = load_run(run_dir)
    if run.prediction is None:
        raise ValueError(f"{run_dir} has no prediction, so it is not a harvest run")
    purpose = run.prediction.values.get("purpose")
    if purpose != "harvest":
        raise ValueError(f"{run_dir} is not a harvest run (its prediction is for {purpose!r})")
    if (run_dir / EXTRACTION).exists():
        raise ValueError(f"{run_dir} is already published; its bits are no longer secret")
    x = shots_of(run)
    seed = seed_bits(2 * len(x))
    extraction = toeplitz_extract(x, seed)
    provenance = {
        "run": run_dir.name,
        "job_id": run.job_id,
        "backend": run.backend,
        "qubit": run.qubits[0],
        "shots": run.shots,
        "entropy_per_bit": extraction.entropy_per_bit,
        "estimate": extraction.estimate,
        "epsilon": extraction.epsilon,
        "input_bits": extraction.input_bits,
        "seed": np.packbits(seed[: extraction.seed_used]).tobytes().hex(),
        "seed_bits": extraction.seed_used,
    }
    batch = pool.add(extraction.bits, provenance, label=run.job_id)
    return Harvest(run_dir, batch, extraction)


def publish(run_dir: Path, pool: Pool) -> Path:
    """Write a harvest run's extraction record next to it, once its batch is spent.

    The record (the batch's provenance, its seed included) lets anyone recompute every bit
    the batch gave, which is what makes a receipt checkable, and also what would make any
    unspent bit predictable. So it is written only after `coin pool` shows the batch empty.
    """
    run = load_run(run_dir)
    if (run_dir / EXTRACTION).exists():
        raise ValueError(f"{run_dir} is already published")
    batches = [b for b in pool.status() if b.provenance.get("job_id") == run.job_id]
    if not batches:
        raise ValueError(f"no batch in the pool came from job {run.job_id}")
    if len(batches) > 1:
        # Possible in pools filled before 0078, when a copied run could be pooled again.
        names = ", ".join(b.batch for b in batches)
        raise ValueError(f"job {run.job_id} was pooled more than once ({names}); publish by hand")
    (batch,) = batches
    if batch.provenance.get("run") != run_dir.name:
        raise ValueError(
            f"batch {batch.batch} came from run {batch.provenance.get('run')}, not {run_dir.name}"
        )
    if batch.remaining:
        raise ValueError(
            f"batch {batch.batch} still has {batch.remaining:,} unspent bits; publishing now "
            "would make them predictable"
        )
    record = {**batch.provenance, "batch": batch.batch, "spent_before_publishing": True}
    return add_record(run_dir, EXTRACTION, record)
