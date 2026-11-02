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

from coin.archive import Prediction, Run, load_run
from coin.circuit import Circuit
from coin.extract import SAFETY, Bits, Extraction, secure_length, seed_bits, toeplitz_extract
from coin.hardware import Submission, Transport, submit
from coin.noise import CalibrationModel, model_from_calibration, predict_tails
from coin.pool import Pool

# The coin in IBM's native gates: H = rz(π/2)·sx·rz(π/2).
NATIVE_COIN = Circuit(1).rz(math.pi / 2, 0).sx(0).rz(math.pi / 2, 0).measure(0, 0)


@dataclass(frozen=True)
class HarvestPlan:
    submission: Submission
    qubit: int
    p_tails: float

    @property
    def expected_bits(self) -> int:
        """About how many bits extraction should yield, if the coin behaves as predicted."""
        h = -math.log2(max(self.p_tails, 1 - self.p_tails))
        return secure_length(self.submission.shots, SAFETY * h)


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
    return HarvestPlan(submission, qubit, p_tails)


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
    if chosen.expected_bits < 1:
        raise ValueError(
            f"{chosen.submission.shots:,} shots would yield no bits after extraction; ask for more"
        )
    pool.require_writable()
    run_dir = submit(transport, chosen.submission, runs_dir, submit_script=submit_script)
    try:
        return extract_run(run_dir, pool)
    except (ValueError, OSError) as error:
        raise HarvestError(
            f"job ran and is archived at {run_dir}, but extraction failed: {error}; "
            f"retry with `coin harvest --from-run {run_dir}`"
        ) from error


class HarvestError(RuntimeError):
    """A harvest's job ran and was archived, but its bits did not reach the pool."""


def extract_run(run_dir: Path, pool: Pool) -> Harvest:
    """Extract an archived one-qubit run's shots and add them to the pool as a batch."""
    run = load_run(run_dir)
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
