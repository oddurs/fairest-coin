"""Hardware runs as archived records: one directory per job, read back as a typed `Run`.

Calibrations drift daily, so no hardware run can be repeated; the archive is the
experiment. The layout is documented file by file in `data/README.md`. Archived runs are
immutable, so the loader reads every run ever written, including the first one, whose
`meta.json` predates this module.
"""

import gzip
import json
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CALIBRATION = "calibration.json.gz"
CIRCUIT = "circuit.qasm"
COUNTS = "counts.json"
MEMORY = "memory.txt"
META = "meta.json"
PREDICTION = "prediction.json"
PREDICTION_DRYRUN = "prediction-dryrun.json"
SUBMIT = "submit.py"
USAGE = "usage.json"

# prediction.json is required unless meta.json records why the run went without one.
REQUIRED = (META, CIRCUIT, COUNTS, CALIBRATION, PREDICTION)
OPTIONAL = (MEMORY, PREDICTION_DRYRUN, SUBMIT, USAGE)

# meta.json keys the typed fields of `Run` own; every other key is kept in `Run.extra`.
_META_KEYS = frozenset(
    {
        "job_id",
        "backend",
        "qubit",
        "qubits",
        "shots",
        "submitted_at",
        "finished_at",
        "quantum_seconds",
        "library_version",
        "no_prediction_reason",
    }
)


class ArchiveError(Exception):
    """A run directory that cannot be read or must not be written."""


@dataclass(frozen=True)
class Prediction:
    """A forecast written down before the job was submitted.

    Only `written_at` is common to every prediction; the rest depends on the model that
    made it, so it is kept as the JSON it was written as.
    """

    written_at: datetime
    values: dict[str, Any]


@dataclass(frozen=True)
class Run:
    """Everything one hardware job left behind."""

    job_id: str
    backend: str
    qubits: tuple[int, ...]
    shots: int
    submitted_at: datetime
    finished_at: datetime
    circuit_qasm: str
    counts: dict[str, int]
    calibration: dict[str, Any]
    prediction: Prediction | None
    # Set only when a run was deliberately submitted without a prediction, and why.
    no_prediction_reason: str | None = None
    prediction_dryrun: Prediction | None = None
    # One outcome string per shot, in shot order, clbit 0 rightmost.
    memory: tuple[str, ...] | None = None
    # As reported at result time. IBM may still say pending then; `usage` is final.
    quantum_seconds: float | None = None
    usage: dict[str, Any] | None = None
    library_version: str | None = None
    submit_script: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def qpu_seconds(self) -> float | None:
        """The QPU time charged: the usage record's charge, else meta.json's quantum_seconds."""
        if self.usage is not None and self.usage.get("qpu_charge_time_seconds") is not None:
            return self.usage["qpu_charge_time_seconds"]
        return self.quantum_seconds

    @property
    def directory_name(self) -> str:
        """`<UTC date of submission>-<job id>`, the run's directory under `data/runs/`."""
        return f"{self.submitted_at.astimezone(UTC).date().isoformat()}-{self.job_id}"


def load_run(path: Path | str) -> Run:
    """Read a run directory. A missing or malformed file raises `ArchiveError` naming it."""
    root = Path(path)
    meta = _read_json(root / META)
    if not isinstance(meta, dict):
        raise ArchiveError(f"{root / META}: expected a JSON object")

    def need(key: str, kind: type | tuple[type, ...]) -> Any:
        value = meta.get(key)
        # bool is an int to isinstance, but true is never a shot count.
        if not isinstance(value, kind) or isinstance(value, bool):
            raise ArchiveError(f"{root / META}: {key!r} is missing or of the wrong type")
        return value

    def maybe(key: str, kind: type | tuple[type, ...]) -> Any:
        return None if meta.get(key) is None else need(key, kind)

    # The first run recorded a single "qubit"; later runs record the list as "qubits".
    if "qubits" in meta:
        qubits_raw = need("qubits", list)
        if not all(isinstance(q, int) and not isinstance(q, bool) for q in qubits_raw):
            raise ArchiveError(f"{root / META}: 'qubits' must be a list of integers")
        qubits = tuple(qubits_raw)
    else:
        qubits = (need("qubit", int),)
    shots = need("shots", int)
    quantum_seconds = maybe("quantum_seconds", (int, float))
    no_prediction_reason = maybe("no_prediction_reason", str)
    if (root / PREDICTION).exists() or no_prediction_reason is None:
        prediction = _read_prediction(root / PREDICTION)
    else:
        prediction = None

    counts_path = _locate(root, COUNTS)
    if counts_path is None:
        raise ArchiveError(f"{root / COUNTS}: required file is missing")
    counts = _read_counts(counts_path, shots)
    memory_path = _locate(root, MEMORY)
    memory = None if memory_path is None else _read_memory(memory_path, counts, shots)

    return Run(
        job_id=need("job_id", str),
        backend=need("backend", str),
        qubits=qubits,
        shots=shots,
        submitted_at=_parse_time(root / META, need("submitted_at", str)),
        finished_at=_parse_time(root / META, need("finished_at", str)),
        circuit_qasm=_read_text(root / CIRCUIT),
        counts=counts,
        calibration=_read_calibration(root / CALIBRATION),
        prediction=prediction,
        no_prediction_reason=no_prediction_reason,
        prediction_dryrun=_optional(root / PREDICTION_DRYRUN, _read_prediction),
        memory=memory,
        quantum_seconds=quantum_seconds,
        usage=_optional(root / USAGE, _read_object),
        library_version=maybe("library_version", str),
        submit_script=_optional(root / SUBMIT, _read_text),
        extra={k: v for k, v in meta.items() if k not in _META_KEYS},
    )


def write_run(runs_dir: Path | str, run: Run, *, allow_no_prediction: bool = False) -> Path:
    """Write `run` to `runs_dir/<run.directory_name>` and return that directory.

    Refuses, before touching the disk, a run without a prediction (unless
    `allow_no_prediction` is set and the run says why in `no_prediction_reason`), a
    prediction not written strictly before submission, and an existing directory.
    """
    _check_writable(run, allow_no_prediction=allow_no_prediction)
    target = Path(runs_dir) / run.directory_name
    if target.exists():
        raise ArchiveError(f"{target}: already exists; archived runs are never overwritten")

    meta: dict[str, Any] = {
        **run.extra,
        "job_id": run.job_id,
        "backend": run.backend,
        "qubits": list(run.qubits),
        "shots": run.shots,
        "submitted_at": _format_time(run.submitted_at),
        "finished_at": _format_time(run.finished_at),
        "quantum_seconds": run.quantum_seconds,
    }
    if run.library_version is not None:
        meta["library_version"] = run.library_version
    if run.no_prediction_reason is not None:
        meta["no_prediction_reason"] = run.no_prediction_reason

    # Write into a hidden staging directory and rename it into place: a run appears whole or
    # not at all, so a failure halfway can never leave a partial run blocking its own retry.
    Path(runs_dir).mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{run.directory_name}.", dir=runs_dir))
    try:
        _write_json(staging / META, meta)
        (staging / CIRCUIT).write_text(run.circuit_qasm)
        # Whole-chip runs have ~100,000 distinct 156-bit outcomes: gzip keeps them committable.
        _write_gzip(staging / f"{COUNTS}.gz", _dump_json(run.counts))
        # mtime=0 keeps the bytes a function of the calibration alone, so git sees no churn.
        (staging / CALIBRATION).write_bytes(gzip.compress(_dump_json(run.calibration), mtime=0))
        if run.prediction is not None:
            _write_json(staging / PREDICTION, _prediction_json(run.prediction))
        if run.prediction_dryrun is not None:
            _write_json(staging / PREDICTION_DRYRUN, _prediction_json(run.prediction_dryrun))
        if run.memory is not None:
            _write_gzip(staging / f"{MEMORY}.gz", ("".join(run.memory) + "\n").encode())
        if run.usage is not None:
            _write_json(staging / USAGE, run.usage)
        if run.submit_script is not None:
            (staging / SUBMIT).write_text(run.submit_script)
        staging.rename(target)
    except BaseException:
        # Best effort: the original error is the one worth reporting.
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def _check_writable(run: Run, *, allow_no_prediction: bool) -> None:
    times = {"submitted_at": run.submitted_at, "finished_at": run.finished_at}
    for label, prediction in (("prediction", run.prediction), ("dry run", run.prediction_dryrun)):
        if prediction is not None:
            times[f"{label} written_at"] = prediction.written_at
    for label, when in times.items():
        if when.tzinfo is None:
            raise ArchiveError(f"{label} must be timezone-aware, got {when.isoformat()}")

    if run.prediction is None:
        if not allow_no_prediction:
            raise ArchiveError(
                f"run {run.job_id} has no prediction; a prediction is written before the "
                "measurement it predicts (pass allow_no_prediction=True to archive it anyway)"
            )
        if not run.no_prediction_reason:
            raise ArchiveError(f"run {run.job_id} has no prediction and no no_prediction_reason")
    elif run.no_prediction_reason is not None:
        raise ArchiveError(f"run {run.job_id} has a prediction and a no_prediction_reason")
    elif run.prediction.written_at >= run.submitted_at:
        raise ArchiveError(
            f"run {run.job_id}: prediction written at {_format_time(run.prediction.written_at)}, "
            f"not before submission at {_format_time(run.submitted_at)}"
        )

    if sum(run.counts.values()) != run.shots:
        raise ArchiveError(
            f"run {run.job_id}: counts sum to {sum(run.counts.values())}, not {run.shots} shots"
        )
    if run.memory is not None and Counter(run.memory) != Counter(run.counts):
        raise ArchiveError(f"run {run.job_id}: memory does not tally to counts")
    overlap = _META_KEYS & run.extra.keys()
    if overlap:
        raise ArchiveError(f"run {run.job_id}: extra repeats typed fields {sorted(overlap)}")


def _format_time(when: datetime) -> str:
    # Microseconds, because the first run's prediction and submission shared a second.
    return when.astimezone(UTC).isoformat(timespec="microseconds")


def _parse_time(path: Path, text: str) -> datetime:
    try:
        when = datetime.fromisoformat(text)
    except ValueError as err:
        raise ArchiveError(f"{path}: {text!r} is not an ISO-8601 timestamp") from err
    if when.tzinfo is None:
        raise ArchiveError(f"{path}: {text!r} has no timezone")
    return when


def _read_text(path: Path) -> str:
    try:
        raw = path.read_bytes()
        return (gzip.decompress(raw) if path.suffix == ".gz" else raw).decode()
    except FileNotFoundError as err:
        raise ArchiveError(f"{path}: required file is missing") from err
    except (OSError, EOFError, UnicodeDecodeError) as err:
        raise ArchiveError(f"{path}: cannot read: {err}") from err


def _locate(root: Path, name: str) -> Path | None:
    """`name` or `name.gz` in `root`, whichever exists; both at once is ambiguous."""
    plain, packed = root / name, root / f"{name}.gz"
    if plain.exists() and packed.exists():
        raise ArchiveError(f"{plain} and {packed} both exist; a run keeps one form of each file")
    return packed if packed.exists() else plain if plain.exists() else None


def _write_gzip(path: Path, data: bytes) -> None:
    # mtime=0 keeps the bytes a function of the data alone, so git sees no churn. Level 6, not
    # the default 9: on random bit strings level 9's match search takes 88 s for 16 MB against
    # 2.7 s at level 6, for a file only 6% smaller.
    path.write_bytes(gzip.compress(data, compresslevel=6, mtime=0))


def _parse_json(path: Path, text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise ArchiveError(f"{path}: malformed JSON: {err}") from err


def _read_json(path: Path) -> Any:
    return _parse_json(path, _read_text(path))


def _read_object(path: Path) -> dict[str, Any]:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ArchiveError(f"{path}: expected a JSON object")
    return data


def _read_calibration(path: Path) -> dict[str, Any]:
    try:
        raw = gzip.decompress(path.read_bytes())
    except FileNotFoundError as err:
        raise ArchiveError(f"{path}: required file is missing") from err
    except (OSError, EOFError) as err:
        raise ArchiveError(f"{path}: not readable gzip: {err}") from err
    try:
        text = raw.decode()
    except UnicodeDecodeError as err:
        raise ArchiveError(f"{path}: not UTF-8: {err}") from err
    data = _parse_json(path, text)
    if not isinstance(data, dict):
        raise ArchiveError(f"{path}: expected a JSON object")
    return data


def _read_prediction(path: Path) -> Prediction:
    data = _read_object(path)
    written_at = data.get("written_at")
    if not isinstance(written_at, str):
        raise ArchiveError(f"{path}: 'written_at' missing or not a string")
    values = {k: v for k, v in data.items() if k != "written_at"}
    return Prediction(_parse_time(path, written_at), values)


def _prediction_json(prediction: Prediction) -> dict[str, Any]:
    return {**prediction.values, "written_at": _format_time(prediction.written_at)}


def _read_counts(path: Path, shots: int) -> dict[str, int]:
    data = _read_object(path)
    if not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in data.values()):
        raise ArchiveError(f"{path}: every count must be a non-negative integer")
    if len({len(k) for k in data}) > 1 or not all(set(k) <= {"0", "1"} for k in data):
        raise ArchiveError(f"{path}: outcomes must be bit strings of one width")
    if sum(data.values()) != shots:
        raise ArchiveError(f"{path}: counts sum to {sum(data.values())}, not {shots} shots")
    return data


def _read_memory(path: Path, counts: dict[str, int], shots: int) -> tuple[str, ...]:
    # Per-shot outcomes are stored concatenated on one line; the width comes from counts.
    bits = _read_text(path).strip()
    width = len(next(iter(counts)))
    if len(bits) != width * shots or not set(bits) <= {"0", "1"}:
        raise ArchiveError(
            f"{path}: expected {shots} outcomes of {width} bit(s), got {len(bits)} characters"
        )
    memory = tuple(bits[i : i + width] for i in range(0, len(bits), width))
    if Counter(memory) != Counter(counts):
        raise ArchiveError(f"{path}: per-shot outcomes do not tally to {COUNTS}")
    return memory


def _optional[T](path: Path, read: Callable[[Path], T]) -> T | None:
    return read(path) if path.exists() else None


def _dump_json(data: object) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def _write_json(path: Path, data: object) -> None:
    path.write_bytes(_dump_json(data))
