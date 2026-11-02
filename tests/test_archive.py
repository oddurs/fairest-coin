import dataclasses
import gzip
import shutil
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from coin import archive
from coin.archive import ArchiveError, Prediction, Run, load_run, write_run

FIRST_RUN = Path(__file__).parent.parent / "data" / "runs" / "2026-11-01-dbjsk29ffo6c73baaosg"

SUBMITTED = datetime(2026, 11, 2, 9, 30, 0, 123456, tzinfo=UTC)

COIN_QASM = """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];
"""


def make_run(**changes: object) -> Run:
    """A two-qubit run with every optional file present, small enough to read in a diff."""
    run = Run(
        job_id="testjob0000000000001",
        backend="ibm_fez",
        qubits=(3, 7),
        shots=6,
        submitted_at=SUBMITTED,
        finished_at=SUBMITTED + timedelta(seconds=8),
        circuit_qasm=COIN_QASM,
        counts={"00": 3, "01": 2, "10": 1},
        calibration={"backend_name": "ibm_fez", "qubits": [[{"name": "T1", "value": 1e-4}]]},
        prediction=Prediction(
            SUBMITTED - timedelta(microseconds=1), {"p_tails": 0.5, "model": "ideal H"}
        ),
        prediction_dryrun=Prediction(SUBMITTED - timedelta(minutes=5), {"p_tails": 0.5}),
        memory=("00", "01", "00", "10", "01", "00"),
        quantum_seconds=None,
        usage={"qpu_charge_time_seconds": 2, "status": "complete"},
        library_version="0.1.0",
        submit_script="print('submitted')\n",
        extra={"transpiled_ops": {"measure": 2, "rz": 2, "sx": 1}},
    )
    return dataclasses.replace(run, **changes)


MINIMAL = {
    "prediction_dryrun": None,
    "memory": None,
    "usage": None,
    "library_version": None,
    "submit_script": None,
    "extra": {},
}


@pytest.mark.parametrize("changes", [{}, MINIMAL], ids=["every-file", "required-files-only"])
def test_round_trip(tmp_path: Path, changes: dict[str, object]) -> None:
    run = make_run(**changes)
    directory = write_run(tmp_path, run)
    assert directory == tmp_path / "2026-11-02-testjob0000000000001"
    assert load_run(directory) == run


def test_round_trip_without_a_prediction(tmp_path: Path) -> None:
    run = make_run(prediction=None, no_prediction_reason="readout check, nothing to forecast")
    assert load_run(write_run(tmp_path, run, allow_no_prediction=True)) == run


def test_timestamps_are_utc_with_microseconds(tmp_path: Path) -> None:
    oslo = timezone(timedelta(hours=1))
    run = make_run(submitted_at=SUBMITTED.astimezone(oslo))
    meta = (write_run(tmp_path, run) / "meta.json").read_text()
    assert '"submitted_at": "2026-11-02T09:30:00.123456+00:00"' in meta


def test_the_directory_is_named_for_the_utc_date(tmp_path: Path) -> None:
    late_evening_in_brazil = datetime(2026, 11, 2, 22, 0, tzinfo=timezone(timedelta(hours=-3)))
    run = make_run(submitted_at=late_evening_in_brazil, finished_at=late_evening_in_brazil)
    assert write_run(tmp_path, run).name == "2026-11-03-testjob0000000000001"


def test_calibration_is_gzipped_reproducibly(tmp_path: Path) -> None:
    first = write_run(tmp_path / "a", make_run()) / "calibration.json.gz"
    second = write_run(tmp_path / "b", make_run()) / "calibration.json.gz"
    assert not (first.parent / "calibration.json").exists()
    assert first.read_bytes() == second.read_bytes()


def test_the_first_run() -> None:
    run = load_run(FIRST_RUN)
    assert run.job_id == "dbjsk29ffo6c73baaosg"
    assert run.backend == "ibm_marrakesh"
    assert run.qubits == (139,)
    assert run.shots == 4096
    assert sum(run.counts.values()) == 4096
    assert run.counts == {"0": 2025, "1": 2071}
    assert run.memory is not None
    assert len(run.memory) == 4096
    assert run.calibration["backend_name"] == "ibm_marrakesh"
    assert run.circuit_qasm.startswith("OPENQASM 3.0;")
    assert run.submit_script is not None
    assert run.prediction_dryrun is not None


def test_the_first_runs_prediction_came_first() -> None:
    run = load_run(FIRST_RUN)
    assert run.prediction is not None
    # The local clocks had second resolution, so prediction and submission share a second;
    # IBM's own record of the job's creation, to the microsecond, is strictly later.
    assert run.prediction.written_at <= run.submitted_at
    created = datetime.fromisoformat(run.extra["timestamps"]["created"])
    assert run.prediction.written_at < created


def test_the_first_runs_qpu_time_comes_from_the_final_usage_record() -> None:
    run = load_run(FIRST_RUN)
    assert run.quantum_seconds is None
    assert run.extra["usage"]["status"] == "pending"
    assert run.qpu_seconds == 3


def on_disk(directory: Path, name: str) -> Path:
    """The file a run actually wrote for `name`: plain, or gzipped for counts and memory."""
    packed = directory / f"{name}.gz"
    return packed if packed.exists() else directory / name


def overwrite(path: Path, text: str) -> None:
    path.write_bytes(gzip.compress(text.encode()) if path.suffix == ".gz" else text.encode())


@pytest.mark.parametrize("name", archive.REQUIRED)
def test_a_missing_required_file_is_named(tmp_path: Path, name: str) -> None:
    directory = write_run(tmp_path, make_run())
    on_disk(directory, name).unlink()
    with pytest.raises(ArchiveError, match=name):
        load_run(directory)


@pytest.mark.parametrize("name", archive.OPTIONAL)
def test_an_optional_file_may_be_absent(tmp_path: Path, name: str) -> None:
    directory = write_run(tmp_path, make_run())
    on_disk(directory, name).unlink()
    assert load_run(directory).job_id == "testjob0000000000001"


@pytest.mark.parametrize(
    "name", ["meta.json", "counts.json", "prediction.json", "prediction-dryrun.json", "usage.json"]
)
def test_malformed_json_is_named(tmp_path: Path, name: str) -> None:
    directory = write_run(tmp_path, make_run())
    target = on_disk(directory, name)
    overwrite(target, '{"shots": 6,')
    with pytest.raises(ArchiveError, match="malformed JSON"):
        load_run(directory)


def test_malformed_calibration_is_named(tmp_path: Path) -> None:
    directory = write_run(tmp_path, make_run())
    (directory / "calibration.json.gz").write_bytes(gzip.compress(b"{not json"))
    with pytest.raises(ArchiveError, match=r"calibration\.json\.gz"):
        load_run(directory)


def test_calibration_that_is_not_gzip_is_named(tmp_path: Path) -> None:
    directory = write_run(tmp_path, make_run())
    (directory / "calibration.json.gz").write_text("{}")
    with pytest.raises(ArchiveError, match=r"calibration\.json\.gz"):
        load_run(directory)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("memory.txt", "0001\n"),
        ("memory.txt", "111111111111\n"),
        ("counts.json", '{"00": 6, "01": 1}'),
        ("meta.json", '{"job_id": "x"}'),
    ],
    ids=["memory-short", "memory-disagrees-with-counts", "counts-exceed-shots", "meta-sparse"],
)
def test_an_inconsistent_file_is_named(tmp_path: Path, name: str, content: str) -> None:
    directory = write_run(tmp_path, make_run())
    overwrite(on_disk(directory, name), content)
    with pytest.raises(ArchiveError, match=name):
        load_run(directory)


def test_a_copied_first_run_loads_like_the_original(tmp_path: Path) -> None:
    copy = tmp_path / FIRST_RUN.name
    shutil.copytree(FIRST_RUN, copy)
    assert load_run(copy) == load_run(FIRST_RUN)


def test_a_run_without_a_prediction_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ArchiveError, match="no prediction"):
        write_run(tmp_path, make_run(prediction=None))
    assert list(tmp_path.iterdir()) == []


def test_opting_out_of_a_prediction_needs_a_reason(tmp_path: Path) -> None:
    with pytest.raises(ArchiveError, match="no_prediction_reason"):
        write_run(tmp_path, make_run(prediction=None), allow_no_prediction=True)


@pytest.mark.parametrize("after", [timedelta(0), timedelta(microseconds=1), timedelta(hours=1)])
def test_a_prediction_not_before_submission_is_refused(tmp_path: Path, after: timedelta) -> None:
    late = Prediction(SUBMITTED + after, {"p_tails": 0.5})
    with pytest.raises(ArchiveError, match="not before submission"):
        write_run(tmp_path, make_run(prediction=late))
    assert list(tmp_path.iterdir()) == []


def test_naive_timestamps_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ArchiveError, match="timezone-aware"):
        write_run(tmp_path, make_run(submitted_at=SUBMITTED.replace(tzinfo=None)))


@pytest.mark.parametrize(
    "changes",
    [
        {"counts": {"00": 5}},
        {"memory": ("00",) * 6},
        {"extra": {"shots": 6}},
    ],
    ids=["counts-miss-shots", "memory-disagrees-with-counts", "extra-shadows-a-field"],
)
def test_an_inconsistent_run_is_refused(tmp_path: Path, changes: dict[str, object]) -> None:
    with pytest.raises(ArchiveError):
        write_run(tmp_path, make_run(**changes))
    assert list(tmp_path.iterdir()) == []


def test_an_existing_run_is_never_overwritten(tmp_path: Path) -> None:
    directory = write_run(tmp_path, make_run())
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(ArchiveError, match="already exists"):
        write_run(tmp_path, make_run(counts={"00": 6}, memory=None))
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_the_layout_names_match_the_first_run() -> None:
    assert {*archive.REQUIRED, *archive.OPTIONAL} == {p.name for p in FIRST_RUN.iterdir()}


def test_a_failure_halfway_leaves_nothing_and_the_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = make_run()

    def disk_full(*_args: object, **_kwargs: object) -> bytes:
        raise OSError("No space left on device")

    # The calibration is written after meta, circuit and counts: a genuine partial write.
    monkeypatch.setattr(archive.gzip, "compress", disk_full)
    with pytest.raises(OSError, match="No space"):
        write_run(tmp_path, run)
    assert list(tmp_path.iterdir()) == []

    monkeypatch.undo()
    assert load_run(write_run(tmp_path, run)) == run


def test_new_runs_gzip_counts_and_memory(tmp_path: Path) -> None:
    directory = write_run(tmp_path, make_run())
    names = {path.name for path in directory.iterdir()}
    assert {"counts.json.gz", "memory.txt.gz"} <= names
    assert not {"counts.json", "memory.txt"} & names


@pytest.mark.parametrize("name", ["counts.json", "memory.txt"])
def test_both_forms_of_one_file_are_refused(tmp_path: Path, name: str) -> None:
    directory = write_run(tmp_path, make_run())
    shutil.copy(on_disk(directory, name), directory / name)
    with pytest.raises(ArchiveError, match="both exist"):
        load_run(directory)


def test_a_whole_chip_run_stays_small(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    shots, width = 100_000, 156
    bits = rng.integers(0, 2, size=(shots, width), dtype=np.uint8)
    memory = tuple("".join(map(str, row)) for row in bits)
    run = make_run(
        shots=shots, memory=memory, counts=dict(Counter(memory)), qubits=tuple(range(width))
    )
    directory = write_run(tmp_path, run)
    size = sum(path.stat().st_size for path in directory.iterdir())
    assert size < 6_000_000, f"{size / 1e6:.1f} MB"
    assert load_run(directory) == run


def test_a_record_added_later_is_written_whole_and_only_once(tmp_path: Path) -> None:
    run = tmp_path / FIRST_RUN.name
    shutil.copytree(FIRST_RUN, run)
    path = archive.add_record(run, archive.EXTRACTION, {"bits": 3})
    assert path.read_text() == '{\n  "bits": 3\n}\n'
    assert not list(run.glob(".*.tmp"))
    with pytest.raises(archive.ArchiveError, match="already exists"):
        archive.add_record(run, archive.EXTRACTION, {"bits": 4})
    with pytest.raises(archive.ArchiveError, match="not a record"):
        archive.add_record(run, archive.META, {})
    assert archive.load_run(run).job_id  # the run itself is untouched and still loads
