"""Running a circuit on real hardware: check the prediction, submit, archive. No Qiskit here.

The order is the point. A prediction is written down before the measurement it predicts, so
`submit` refuses before anything reaches the hardware if there is no prediction or it was
not written first; QPU seconds are too scarce to spend on a run that cannot be archived.
The transport, real or fake, only carries a circuit there and the shots back.
"""

import json
import os
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from coin import __version__
from coin.archive import ArchiveError, Prediction, Run, write_run
from coin.circuit import Circuit
from coin.compile import to_qasm


@dataclass(frozen=True)
class JobResult:
    """What came back from one job, in the project's conventions."""

    job_id: str
    submitted_at: datetime
    finished_at: datetime
    # One outcome string per shot, in shot order, classical bit 0 rightmost.
    memory: tuple[str, ...]
    quantum_seconds: float | None
    usage: dict[str, Any] | None
    # What actually ran: the gate counts after mapping, and the execution options in force.
    executed_ops: dict[str, int]
    options: dict[str, Any]


class Transport(Protocol):
    """Carries circuits to a backend and results back."""

    def calibration(self, backend: str) -> dict[str, Any]: ...

    def run(self, backend: str, qasm: str, layout: Sequence[int], shots: int) -> JobResult: ...


@dataclass(frozen=True)
class Submission:
    """One planned hardware run, checked before anything reaches the hardware.

    `calibration` is the snapshot the prediction was made from; it is archived with the run.
    The circuit must already be in native gates, and `layout[i]` is the physical qubit that
    runs virtual qubit i.
    """

    circuit: Circuit
    backend: str
    layout: tuple[int, ...]
    shots: int
    calibration: dict[str, Any]
    prediction: Prediction

    def __post_init__(self) -> None:
        if len(self.layout) != self.circuit.n_qubits or len(set(self.layout)) != len(self.layout):
            raise ValueError(
                f"layout {list(self.layout)} must name {self.circuit.n_qubits} distinct qubits"
            )
        if self.shots < 1:
            raise ValueError(f"shots must be at least 1, got {self.shots}")
        to_qasm(self.circuit)  # raises now if anything is not native


def submit(
    transport: Transport,
    submission: Submission,
    runs_dir: Path,
    submit_script: str | None = None,
) -> Path:
    """Run `submission` and archive everything; return the archived run's directory."""
    written = submission.prediction.written_at
    # Checked at the last moment, not at planning time: the prediction must predate the job.
    if written.tzinfo is None or written >= datetime.now(UTC):
        raise ValueError("the prediction must be written, with a timezone, before submission")
    qasm = to_qasm(submission.circuit)
    # Everything that could stop the run being archived is checked while it is still free.
    _require_writable(runs_dir)
    for label, data in (
        ("calibration", submission.calibration),
        ("prediction", submission.prediction.values),
    ):
        try:
            json.dumps(data)
        except (TypeError, ValueError) as error:
            raise ValueError(f"the {label} cannot be archived as JSON: {error}") from error

    result = transport.run(submission.backend, qasm, submission.layout, submission.shots)
    try:
        return _archive(submission, result, qasm, runs_dir, submit_script)
    except Exception as error:
        # The QPU time is spent: whatever went wrong, keep the shots and say where they are.
        saved = _save_unarchived(runs_dir, submission, result)
        raise ArchiveError(
            f"job {result.job_id} ran but could not be archived ({error}); "
            f"its raw result is in {saved}"
        ) from error


def _archive(
    submission: Submission,
    result: JobResult,
    qasm: str,
    runs_dir: Path,
    submit_script: str | None,
) -> Path:
    run = Run(
        job_id=result.job_id,
        backend=submission.backend,
        qubits=submission.layout,
        shots=submission.shots,
        submitted_at=result.submitted_at,
        finished_at=result.finished_at,
        circuit_qasm=qasm,
        counts=dict(Counter(result.memory)),
        calibration=submission.calibration,
        prediction=submission.prediction,
        memory=result.memory,
        quantum_seconds=result.quantum_seconds,
        usage=result.usage,
        library_version=__version__,
        submit_script=submit_script,
        extra={"executed_ops": result.executed_ops, "options": result.options},
    )
    return write_run(runs_dir, run)


def _require_writable(runs_dir: Path) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(runs_dir, os.W_OK):
        raise ValueError(f"{runs_dir} is not writable, so a run there could not be archived")


def _save_unarchived(runs_dir: Path, submission: Submission, result: JobResult) -> Path:
    """Dump a finished job's raw result where it can be recovered by hand."""
    record = {
        "job_id": result.job_id,
        "backend": submission.backend,
        "layout": list(submission.layout),
        "shots": submission.shots,
        "submitted_at": result.submitted_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "memory": list(result.memory),
        "usage": result.usage,
        "prediction_written_at": submission.prediction.written_at.isoformat(),
        "prediction": submission.prediction.values,
    }
    text = json.dumps(record, default=str)
    for directory in (runs_dir, Path(tempfile.gettempdir())):
        target = directory / f".unarchived-{result.job_id}.json"
        try:
            target.write_text(text)
        except OSError:
            continue
        return target
    raise ArchiveError(f"job {result.job_id}: its raw result could not be saved anywhere")
