"""Running a circuit on real hardware: check the prediction, submit, archive. No Qiskit here.

The order is the point. A prediction is written down before the measurement it predicts, so
`submit` refuses before anything reaches the hardware if there is no prediction or it was
not written first; QPU seconds are too scarce to spend on a run that cannot be archived.
The transport, real or fake, only carries a circuit there and the shots back.

Nothing a job needs to be archived lives only in memory while the job runs. Before
submitting, `submit` writes a pending record (the plan, the calibration, the prediction)
next to the archive. If anything goes wrong once the hardware has the job (the wait times
out, the connection drops, someone presses Ctrl-C, archiving fails) the record keeps the
job id, and `recover` archives the run from it later, with the prediction it was given.
A transport reports the job id the moment the hardware assigns it (`on_submitted`), and
marks a failure that came after that by giving the exception a `job_id` attribute.
"""

import contextlib
import fcntl
import json
import os
import re
import stat
import uuid
from collections import Counter
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from coin import __version__, durable
from coin.archive import ArchiveError, Prediction, Run, write_run
from coin.circuit import Circuit
from coin.compile import coupled_pairs, require_coupled, to_qasm


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

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> JobResult:
        """Run and return the result.

        Call `on_submitted(job_id, details)` as soon as the job exists, where details holds
        `submitted_at` (ISO 8601), `executed_ops` and `options`: what a recovered run will need.
        """
        ...


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
        require_coupled(self.circuit, self.layout, coupled_pairs(self.calibration))


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

    record = _new_record(runs_dir, submission, qasm, submit_script)
    pending = runs_dir / f".pending-{uuid.uuid4().hex}.json"
    # Written before submission, so a disk that cannot take it stops the run while it is free.
    _write_json_atomic(pending, record)

    def on_submitted(job_id: str, details: dict[str, Any]) -> None:
        # Recorded the moment the job exists: a closed terminal or a killed process during a
        # long queue raises nothing, so the record must already name the job. Best effort:
        # if the disk refuses, the id stays in memory and the error path still reports it.
        record.update(job_id=job_id, **details)
        with contextlib.suppress(OSError):
            _write_json_atomic(pending, record)

    # The lock tells `recover` this process is still waiting on the job.
    with _waiting(pending):
        try:
            result = transport.run(
                submission.backend, qasm, submission.layout, submission.shots, on_submitted
            )
        except BaseException as error:
            _note_lost(error, record, pending)
            raise
        return _archive_or_keep(pending, record, result, runs_dir)


def _note_lost(error: BaseException, record: dict[str, Any], pending: Path) -> None:
    """Keep or drop the pending record after `transport.run` failed, and say what to do."""
    job_id = getattr(error, "job_id", None) or record.get("job_id")
    if job_id is None:
        if getattr(error, "maybe_submitted", False):
            error.add_note(
                f"the job may have reached the hardware before IBM returned its id; its plan "
                f"is kept in {pending}. Find the job id on IBM's dashboard, then "
                f"`coin recover JOB_ID --record {pending}` archives it."
            )
            return
        # Failed before the hardware had the job: nothing ran, nothing to keep.
        pending.unlink(missing_ok=True)
        return
    # The note first: it must reach the user even if the disk refuses everything below.
    error.add_note(
        f"job {job_id} is on the hardware; once it finishes, `coin recover {job_id}` archives "
        f"it with the prediction it was given (kept in {pending})."
    )
    record["job_id"] = job_id
    try:
        _write_json_atomic(pending, record)
    except OSError as failure:
        error.add_note(
            f"the record could not be updated ({failure}); "
            f"`coin recover {job_id} --record {pending}` attaches the id"
        )


# IBM job ids are letters and digits; tests use hyphens too. Never a glob or a path.
_JOB_ID = re.compile(r"[A-Za-z0-9_-]+")
_PENDING = re.compile(r"\.pending-[0-9a-f]+\.json")


class Fetcher(Protocol):
    """Fetches a finished job's result by id: what `recover` needs from a transport."""

    def fetch(self, backend: str, job_id: str, submitted_at: datetime) -> JobResult: ...


@dataclass(frozen=True)
class Pending:
    """A pending record on disk, or why it could not be read."""

    path: Path
    record: dict[str, Any] | None
    problem: str | None = None


def pending_runs(runs_dir: Path) -> list[Pending]:
    """Every pending record for `runs_dir`, including copies kept in this user's fallback
    directory.

    A record that cannot be read, is not a record, or contradicts itself is listed with the
    reason rather than hiding the others. Records another user owns are never trusted: they
    could carry any shots and any prediction.
    """
    found = []
    fallback = _fallback_dir()
    for directory in (runs_dir, *([fallback] if _private(fallback) else [])):
        for path in sorted(directory.glob(".pending-*.json")) if directory.is_dir() else []:
            try:
                owner = path.lstat().st_uid
                record = json.loads(path.read_text())
            except (OSError, ValueError) as error:
                found.append(Pending(path, None, f"unreadable: {error}"))
                continue
            if owner != os.getuid():
                found.append(Pending(path, None, "owned by another user, so not trusted"))
                continue
            if (problem := _record_problem(record)) is not None:
                found.append(Pending(path, None, problem))
                continue
            # A copy in the fallback directory belongs here only if it says so.
            if directory == runs_dir or Path(record.get("runs_dir", "")) == runs_dir.resolve():
                found.append(Pending(path, record))
    return found


def _record_problem(record: object) -> str | None:
    """Why `record` cannot be a pending record, or None."""
    if not isinstance(record, dict):
        return f"not a pending record: {type(record).__name__}, not an object"
    job_id = record.get("job_id")
    if job_id is not None and not (isinstance(job_id, str) and _JOB_ID.fullmatch(job_id)):
        return f"names {job_id!r}, which is not a job id"
    if "result" in record:
        result = record["result"]
        if not isinstance(result, dict) or result.get("job_id") != job_id:
            named = result.get("job_id") if isinstance(result, dict) else None
            return f"is the record for job {job_id} but holds a result for job {named}"
    return None


def recover(
    fetcher: Callable[[], Fetcher],
    job_id: str,
    runs_dir: Path,
    record_path: Path | None = None,
    *,
    force: bool = False,
) -> Path:
    """Archive a job whose run was cut short, from its pending record, into `runs_dir`.

    `fetcher` is called only if the record does not already hold the result. A job already in
    the archive is not archived again; its leftover records are removed. `record_path` names
    a record that never got its job id, and is checked against `job_id`, never overridden.
    A record whose submitting process is still waiting is left alone unless `force`.
    """
    if not _JOB_ID.fullmatch(job_id):
        raise ValueError(f"{job_id!r} is not a job id")
    target = None if record_path is None else record_path.resolve()
    candidates = [
        p
        for p in pending_runs(runs_dir)
        if p.record is not None
        and (p.record.get("job_id") == job_id if target is None else p.path.resolve() == target)
    ]
    if record_path is not None:
        _check_named_record(record_path, candidates, job_id, runs_dir)
    else:
        done = _archived(runs_dir, job_id)
        if done is not None:
            for p in candidates:
                p.path.unlink(missing_ok=True)
            return done
    if not candidates:
        raise ValueError(f"no pending record for job {job_id} for {runs_dir}")
    # Prefer a record that already holds the result; otherwise the newest.
    chosen = max(candidates, key=lambda p: ("result" in (p.record or {}), p.path.stat().st_mtime))
    assert chosen.record is not None
    record: dict[str, Any] = {**chosen.record, "job_id": job_id}
    if not force and _still_waiting(chosen.path):
        raise ValueError(
            f"job {job_id} is still being waited on by the process that submitted it; let it "
            "finish, or pass --force if it is stuck"
        )
    if "result" in record:
        result = _result_from_json(record["result"])
    else:
        fetched = fetcher().fetch(
            record["backend"], job_id, datetime.fromisoformat(record["submitted_at"])
        )
        # What ran is known only at submission; the record kept it.
        result = JobResult(
            job_id=fetched.job_id,
            submitted_at=fetched.submitted_at,
            finished_at=fetched.finished_at,
            memory=fetched.memory,
            quantum_seconds=fetched.quantum_seconds,
            usage=fetched.usage,
            executed_ops=fetched.executed_ops or record.get("executed_ops", {}),
            options=fetched.options or record.get("options", {}),
        )
    directory = _archive_or_keep(chosen.path, record, result, runs_dir)
    for p in candidates:
        p.path.unlink(missing_ok=True)
    return directory


def _check_named_record(
    record_path: Path, candidates: list[Pending], job_id: str, runs_dir: Path
) -> None:
    """A record named with --record must exist, name this job or none, and not be for a job
    already archived: a mistyped id must never cost the only copy of a prediction."""
    if not candidates:
        raise ValueError(f"{record_path} is not a readable pending record for {runs_dir}")
    named = (candidates[0].record or {}).get("job_id")
    if named not in (None, job_id):
        raise ValueError(f"{record_path} is the record for job {named}, not {job_id}")
    if _archived(runs_dir, job_id) is not None:
        raise ValueError(f"job {job_id} is already archived; {record_path} is another job's")


def discard(record_path: Path, *, force: bool = False) -> None:
    """Remove a pending record that will never be archived (a job that never ran).

    A record that names a job or holds its shots is the only copy of that job's prediction,
    so it is refused unless `force`.
    """
    if not _PENDING.fullmatch(record_path.name):
        raise ValueError(f"{record_path} is not a pending record")
    record = json.loads(record_path.read_text())
    if not force and ("job_id" in record or "result" in record):
        raise ValueError(
            f"{record_path} belongs to job {record.get('job_id', '(unknown)')}"
            + (" and holds its shots" if "result" in record else "")
            + "; `coin recover` archives it, or pass --force to throw it away"
        )
    record_path.unlink()


def _new_record(
    runs_dir: Path, submission: Submission, qasm: str, submit_script: str | None
) -> dict[str, Any]:
    return {
        "runs_dir": str(runs_dir.resolve()),
        "backend": submission.backend,
        "layout": list(submission.layout),
        "shots": submission.shots,
        "circuit_qasm": qasm,
        "calibration": submission.calibration,
        "prediction": {
            "written_at": submission.prediction.written_at.isoformat(),
            "values": submission.prediction.values,
        },
        "submit_script": submit_script,
        # Replaced by the transport's own submission time once the job exists.
        "submitted_at": datetime.now(UTC).isoformat(),
    }


@contextmanager
def _waiting(pending: Path) -> Generator[None]:
    """Hold `<record>.lock` while this process waits on the job. The operating system drops
    the lock however the process ends, so a held lock means someone is still waiting."""
    lock = pending.with_suffix(".lock")
    with lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            # A lock left behind is harmless (`_still_waiting` clears one nobody holds), but
            # an error here would replace the one saying where the job's result was kept.
            with contextlib.suppress(OSError):
                lock.unlink(missing_ok=True)


def _still_waiting(pending: Path) -> bool:
    """Whether the process that submitted this record is still waiting on its job."""
    lock = pending.with_suffix(".lock")
    try:
        handle = lock.open("r")
    except FileNotFoundError:
        return False
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    lock.unlink(missing_ok=True)  # left by a process that is gone
    return False


def _archived(runs_dir: Path, job_id: str) -> Path | None:
    """The run already archived for this job, if any: `<date>-<job id>`, exactly, so job
    `abc` is never taken for `x-abc`."""
    name = re.compile(rf"\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(job_id)}")
    runs = sorted(runs_dir.iterdir()) if runs_dir.is_dir() else []
    return next((p for p in runs if p.is_dir() and name.fullmatch(p.name)), None)


def _archive_or_keep(
    pending: Path, record: dict[str, Any], result: JobResult, runs_dir: Path
) -> Path:
    done = _archived(runs_dir, result.job_id)
    if done is not None:
        # Archived already, by a recovery racing this run or before a crash: never twice.
        pending.unlink(missing_ok=True)
        return done
    try:
        directory = _archive(record, result, runs_dir)
    except BaseException as error:
        done = _archived(runs_dir, result.job_id)
        if done is not None and isinstance(error, Exception):
            # Lost a race to another archiver: the run is safe, and only once.
            pending.unlink(missing_ok=True)
            return done
        # The QPU time is spent: keep the result with its plan and say how to finish.
        kept = _keep_result(pending, record, result)
        message = (
            f"job {result.job_id} ran but could not be archived; everything is in {kept}, "
            f"and `coin recover {result.job_id}` retries"
        )
        if isinstance(error, Exception):
            raise ArchiveError(f"{message} ({error})") from error
        error.add_note(message)
        raise
    pending.unlink(missing_ok=True)
    return directory


def _keep_result(pending: Path, record: dict[str, Any], result: JobResult) -> Path:
    full = {**record, "job_id": result.job_id, "result": _result_to_json(result)}
    try:
        _write_json_atomic(pending, full)
    except OSError:
        pass  # the runs directory refuses it; this user's own directory is the last resort
    else:
        return pending
    try:
        fallback = _make_private(_fallback_dir())
        target = fallback / pending.name
        _write_json_atomic(target, full)
    except (OSError, ArchiveError) as error:
        raise ArchiveError(
            f"job {result.job_id}: its result could not be saved anywhere ({error})"
        ) from error
    return target


def _fallback_dir() -> Path:
    """Where a job's record goes when the runs directory refuses it: under the user's state
    directory, never a shared temp directory where another user could read the shots or
    plant a record, and kept across a reboot."""
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "fairest-coin" / "pending"


def _private(directory: Path) -> bool:
    """Whether `directory` is a real directory this user owns that no one else can use."""
    try:
        info = directory.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077


def _make_private(directory: Path) -> Path:
    durable.make_directory(directory.parent)
    with contextlib.suppress(FileExistsError):
        directory.mkdir(mode=0o700)
        durable.sync_directory(directory.parent)
    if not _private(directory):
        raise ArchiveError(f"{directory} is not private to this user, so nothing is kept there")
    return directory


def _result_to_json(result: JobResult) -> dict[str, Any]:
    return {
        "job_id": result.job_id,
        "submitted_at": result.submitted_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "memory": list(result.memory),
        "quantum_seconds": result.quantum_seconds,
        "usage": result.usage,
        "executed_ops": result.executed_ops,
        "options": result.options,
    }


def _result_from_json(data: dict[str, Any]) -> JobResult:
    return JobResult(
        job_id=data["job_id"],
        submitted_at=datetime.fromisoformat(data["submitted_at"]),
        finished_at=datetime.fromisoformat(data["finished_at"]),
        memory=tuple(data["memory"]),
        quantum_seconds=data["quantum_seconds"],
        usage=data["usage"],
        executed_ops=data["executed_ops"],
        options=data["options"],
    )


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write `path` whole or not at all, and durably: it may be all that is left of a job.
    Readable by this user only: a harvest's shots are secret until its batch is spent."""
    durable.replace(path, json.dumps(data, default=str).encode(), mode=0o600)


def _archive(record: dict[str, Any], result: JobResult, runs_dir: Path) -> Path:
    """Write the run from its pending record and its result."""
    run = Run(
        job_id=result.job_id,
        backend=record["backend"],
        qubits=tuple(record["layout"]),
        shots=record["shots"],
        submitted_at=result.submitted_at,
        finished_at=result.finished_at,
        circuit_qasm=record["circuit_qasm"],
        counts=dict(Counter(result.memory)),
        calibration=record["calibration"],
        prediction=Prediction(
            datetime.fromisoformat(record["prediction"]["written_at"]),
            record["prediction"]["values"],
        ),
        memory=result.memory,
        quantum_seconds=result.quantum_seconds,
        usage=result.usage,
        library_version=__version__,
        submit_script=record["submit_script"],
        extra={"executed_ops": result.executed_ops, "options": result.options},
    )
    return write_run(runs_dir, run)


def _require_writable(runs_dir: Path) -> None:
    durable.make_directory(runs_dir)
    if not os.access(runs_dir, os.W_OK):
        raise ValueError(f"{runs_dir} is not writable, so a run there could not be archived")
