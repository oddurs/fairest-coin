import json
import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from coin.archive import ArchiveError, Prediction, load_run
from coin.circuit import Circuit
from coin.hardware import JobResult, Submission, discard, pending_runs, recover, submit

NATIVE_COIN = Circuit(1).rz(math.pi / 2, 0).sx(0).rz(math.pi / 2, 0).measure(0, 0)
CALIBRATION: dict[str, Any] = {"qubits": [], "gates": [], "backend_name": "fake_backend"}


class FakeTransport:
    """Returns a fixed result and records every submission, with no network."""

    def __init__(self, memory: tuple[str, ...]) -> None:
        self.memory = memory
        self.submitted: list[tuple[str, str, list[int], int]] = []

    def calibration(self, backend: str) -> dict[str, Any]:
        return CALIBRATION

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> JobResult:
        self.submitted.append((backend, qasm, list(layout), shots))
        now = datetime.now(UTC)
        return JobResult(
            job_id="fakejob0001",
            submitted_at=now,
            finished_at=now + timedelta(seconds=5),
            memory=self.memory,
            quantum_seconds=None,
            usage={"qpu_charge_time_seconds": 3, "status": "pending"},
            executed_ops={"rz": 2, "sx": 1, "measure": 1},
            options={"twirling": {"enable_gates": False}},
        )


# What a transport reports when the job exists: enough for a recovered run to be faithful.
DETAILS = {
    "executed_ops": {"rz": 2, "sx": 1, "measure": 1},
    "options": {"twirling": {"enable_gates": False}},
}


def details() -> dict[str, Any]:
    """DETAILS, stamped now: the job is submitted after its prediction was written."""
    return {**DETAILS, "submitted_at": datetime.now(UTC).isoformat()}


def prediction(written_at: datetime | None = None) -> Prediction:
    when = written_at or datetime.now(UTC) - timedelta(minutes=5)
    return Prediction(written_at=when, values={"p_tails": 0.4995})


def plan(**changes: Any) -> Submission:
    args: dict[str, Any] = {
        "circuit": NATIVE_COIN,
        "backend": "fake_backend",
        "layout": (139,),
        "shots": 4,
        "calibration": CALIBRATION,
        "prediction": prediction(),
    } | changes
    return Submission(**args)


def go(transport: FakeTransport, tmp_path: Path, **changes: Any) -> Path:
    return submit(transport, plan(**changes), tmp_path)


def test_a_run_is_submitted_and_archived_whole(tmp_path: Path) -> None:
    transport = FakeTransport(("0", "1", "1", "0"))
    directory = go(transport, tmp_path)
    assert transport.submitted == [("fake_backend", transport.submitted[0][1], [139], 4)]
    run = load_run(directory)
    assert run.job_id == "fakejob0001"
    assert run.qubits == (139,)
    assert run.counts == {"0": 2, "1": 2}
    assert run.memory == ("0", "1", "1", "0")
    assert run.prediction == prediction(run.prediction.written_at if run.prediction else None)
    assert run.calibration == CALIBRATION
    assert run.extra["executed_ops"] == {"rz": 2, "sx": 1, "measure": 1}
    assert run.circuit_qasm == transport.submitted[0][1]
    assert "sx q[0];" in run.circuit_qasm


# Each case is a factory, called when the test runs: a timestamp built at collection would
# go stale if the machine slept between collecting and running (0072).
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            lambda: {"prediction": prediction(datetime.now(UTC) + timedelta(hours=1))},
            "before submission",
        ),
        (lambda: {"prediction": prediction(datetime(2026, 1, 1))}, "timezone"),
        (lambda: {"circuit": Circuit(1).h(0).measure(0, 0)}, "h"),
        (lambda: {"layout": (1, 2)}, "distinct qubits"),
        (lambda: {"circuit": Circuit(2).measure_all(), "layout": (5, 5)}, "distinct qubits"),
        (lambda: {"shots": 0}, "at least 1"),
    ],
)
def test_bad_submissions_are_refused_before_reaching_hardware(
    tmp_path: Path, changes: Callable[[], dict[str, Any]], message: str
) -> None:
    transport = FakeTransport(("0",))
    with pytest.raises(ValueError, match=message):
        go(transport, tmp_path, **changes())
    assert transport.submitted == []
    assert list(tmp_path.iterdir()) == []


def test_credentials_never_reach_the_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QISKIT_IBM_TOKEN", "sentinel-token-7f3a9")
    monkeypatch.setenv("QISKIT_IBM_INSTANCE", "crn:sentinel-instance")
    directory = go(FakeTransport(("1",)), tmp_path, shots=1)
    for path in directory.iterdir():
        content = path.read_bytes()
        assert b"sentinel-token-7f3a9" not in content
        assert b"crn:sentinel-instance" not in content


def test_an_unwritable_archive_is_refused_before_submission(tmp_path: Path) -> None:
    blocker = tmp_path / "runs"
    blocker.write_text("a file where the runs directory should be")
    transport = FakeTransport(("0",))
    with pytest.raises(FileExistsError):
        submit(transport, plan(), blocker)
    assert transport.submitted == []


def test_a_calibration_that_cannot_be_archived_is_refused_before_submission(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(("0",))
    with pytest.raises(ValueError, match="calibration cannot be archived"):
        submit(transport, plan(calibration={"when": datetime.now(UTC)}), tmp_path)
    assert transport.submitted == []


def test_a_job_that_cannot_be_archived_keeps_everything_and_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def disk_full(*_args: Any, **_kwargs: Any) -> Path:
        raise OSError("No space left on device")

    monkeypatch.setattr("coin.hardware.write_run", disk_full)
    with pytest.raises(ArchiveError, match="coin recover fakejob0001"):
        submit(FakeTransport(("0", "1", "1", "0")), plan(), tmp_path)
    (pending,) = tmp_path.glob(".pending-*.json")
    record = json.loads(pending.read_text())
    assert record["result"]["memory"] == ["0", "1", "1", "0"]
    assert record["calibration"] == CALIBRATION
    assert record["circuit_qasm"]

    monkeypatch.undo()
    # The shots are in the record, so recovery needs no fetch.
    directory = recover(NoFetch, "fakejob0001", tmp_path)
    run = load_run(directory)
    assert run.memory == ("0", "1", "1", "0")
    assert run.calibration == CALIBRATION
    assert run.extra["executed_ops"] == {"rz": 2, "sx": 1, "measure": 1}
    assert not list(tmp_path.glob(".pending-*.json"))


class NoFetch:
    def fetch(self, backend: str, job_id: str, submitted_at: datetime) -> JobResult:
        raise AssertionError("the record already held the result")


class LostAfterSubmission(FakeTransport):
    """IBM accepted the job, then the wait failed with `failure`."""

    def __init__(self, failure: BaseException) -> None:
        super().__init__(("0", "1", "1", "0"))
        self.failure = failure

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> JobResult:
        self.submitted.append((backend, qasm, list(layout), shots))
        setattr(self.failure, "job_id", "lostjob42")  # noqa: B010 - as IBMTransport does
        raise self.failure

    def fetch(self, backend: str, job_id: str, submitted_at: datetime) -> JobResult:
        assert job_id == "lostjob42"
        now = datetime.now(UTC)
        return JobResult(
            job_id=job_id,
            submitted_at=submitted_at,
            finished_at=now,
            memory=("1", "1", "0", "1"),
            quantum_seconds=3.0,
            usage={"qpu_charge_time_seconds": 3},
            executed_ops={},
            options={},
        )


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("result never came"), ConnectionError("dropped"), KeyboardInterrupt()],
    ids=["timeout", "connection", "ctrl-c"],
)
def test_a_job_lost_after_submission_is_recovered_with_its_prediction(
    tmp_path: Path, failure: BaseException
) -> None:
    transport = LostAfterSubmission(failure)
    submission = plan()
    with pytest.raises(type(failure)) as caught:
        submit(transport, submission, tmp_path)
    assert any("coin recover lostjob42" in note for note in caught.value.__notes__)
    assert [p.record["job_id"] for p in pending_runs(tmp_path) if p.record] == ["lostjob42"]

    run = load_run(recover(lambda: transport, "lostjob42", tmp_path))
    assert run.memory == ("1", "1", "0", "1")
    assert run.prediction == submission.prediction
    assert run.calibration == CALIBRATION
    assert run.prediction is not None
    assert run.prediction.written_at < run.submitted_at
    assert pending_runs(tmp_path) == []


def test_a_failure_before_submission_leaves_nothing(tmp_path: Path) -> None:
    class Refused(FakeTransport):
        def run(
            self,
            backend: str,
            qasm: str,
            layout: Sequence[int],
            shots: int,
            on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
        ) -> JobResult:
            raise ConnectionError("never reached IBM")

    with pytest.raises(ConnectionError):
        submit(Refused(("0",)), plan(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_recovering_an_unknown_job_says_so(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no pending record for job nope"):
        recover(NoFetch, "nope", tmp_path)


def test_the_record_names_the_job_while_it_runs(tmp_path: Path) -> None:
    seen: list[str | None] = []

    class Watched(FakeTransport):
        def run(
            self,
            backend: str,
            qasm: str,
            layout: Sequence[int],
            shots: int,
            on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
        ) -> JobResult:
            assert on_submitted is not None
            on_submitted("fakejob0001", details())
            # As if the process were killed here: what is on disk already?
            seen.extend(p.record.get("job_id") for p in pending_runs(tmp_path) if p.record)
            return super().run(backend, qasm, layout, shots)

    submit(Watched(("0", "1", "1", "0")), plan(), tmp_path)
    assert seen == ["fakejob0001"]
    assert pending_runs(tmp_path) == []


def test_a_job_named_by_the_transport_is_kept_even_if_the_error_does_not_name_it(
    tmp_path: Path,
) -> None:
    class Dies(FakeTransport):
        def run(
            self,
            backend: str,
            qasm: str,
            layout: Sequence[int],
            shots: int,
            on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
        ) -> JobResult:
            assert on_submitted is not None
            on_submitted("namedjob5", details())
            raise OSError("socket closed")

    with pytest.raises(OSError, match="socket closed"):
        submit(Dies(("0",)), plan(), tmp_path)
    assert [p.record["job_id"] for p in pending_runs(tmp_path) if p.record] == ["namedjob5"]


def cli(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    from coin import cli as coin_cli  # noqa: PLC0415 - only these tests drive the CLI

    try:
        code = coin_cli.main(argv)
    except SystemExit as exit_info:
        code = int(exit_info.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def test_coin_recover_lists_and_archives_without_a_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def disk_full(*_args: Any, **_kwargs: Any) -> Path:
        raise OSError("No space left on device")

    monkeypatch.setattr("coin.hardware.write_run", disk_full)
    with pytest.raises(ArchiveError):
        submit(FakeTransport(("0", "1", "1", "0")), plan(), tmp_path)
    monkeypatch.undo()
    monkeypatch.setattr("coin.cli._fetcher", lambda: pytest.fail("needed no connection"))

    code, out, _ = cli(["recover", "--runs-dir", str(tmp_path)], capsys)
    assert code == 0
    assert out.startswith("fakejob0001  fake_backend")
    code, out, err = cli(["recover", "fakejob0001", "--runs-dir", str(tmp_path)], capsys)
    assert code == 0, err
    assert "archived" in out
    assert load_run(next(tmp_path.glob("*fakejob0001"))).memory == ("0", "1", "1", "0")


def test_coin_recover_fetches_a_job_that_never_came_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transport = LostAfterSubmission(TimeoutError("queue"))
    with pytest.raises(TimeoutError):
        submit(transport, plan(), tmp_path)
    monkeypatch.setattr("coin.cli._fetcher", lambda: transport)
    code, _, err = cli(["recover", "lostjob42", "--runs-dir", str(tmp_path)], capsys)
    assert code == 0, err
    assert load_run(next(tmp_path.glob("*lostjob42"))).memory == ("1", "1", "0", "1")


def test_coin_recover_names_an_unknown_job(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = cli(["recover", "nope", "--runs-dir", str(tmp_path)], capsys)
    assert code == 1
    assert "no pending record for job nope" in err


class Submits(FakeTransport):
    """Reports the job the moment it exists, then fails the wait with `failure`."""

    def __init__(self, failure: BaseException | None = None, job_id: str = "jobX") -> None:
        super().__init__(("0", "1", "1", "0"))
        self.failure = failure
        self.job_id = job_id

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> JobResult:
        assert on_submitted is not None
        self.reported = details()
        on_submitted(self.job_id, self.reported)
        if self.failure is not None:
            raise self.failure
        result = super().run(backend, qasm, layout, shots)
        return replace(result, job_id=self.job_id)

    def fetch(self, backend: str, job_id: str, submitted_at: datetime) -> JobResult:
        now = datetime.now(UTC)
        return JobResult(
            job_id=job_id,
            submitted_at=submitted_at,
            finished_at=now,
            memory=("1", "0", "0", "1"),
            quantum_seconds=None,
            usage=None,
            executed_ops={},
            options={},
        )


def test_a_disk_that_refuses_the_job_id_still_names_the_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import coin.hardware  # noqa: PLC0415 - patched for this test only

    real = coin.hardware._write_json_atomic
    calls = {"n": 0}

    def fails_after_first(path: Path, data: dict[str, Any]) -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("No space left on device")
        real(path, data)

    monkeypatch.setattr(coin.hardware, "_write_json_atomic", fails_after_first)
    with pytest.raises(TimeoutError) as caught:
        submit(Submits(TimeoutError("queue")), plan(), tmp_path)
    notes = "\n".join(caught.value.__notes__)
    assert "coin recover jobX" in notes
    assert "--record" in notes  # the id could not be saved, so say how to attach it


def test_a_recovered_run_records_what_ran_and_when(tmp_path: Path) -> None:
    transport = Submits(TimeoutError("queue"))
    with pytest.raises(TimeoutError):
        submit(transport, plan(), tmp_path)
    run = load_run(recover(lambda: transport, "jobX", tmp_path))
    # Kept in the record when the job was reported, since a fetch cannot know them.
    assert run.extra["executed_ops"] == DETAILS["executed_ops"]
    assert run.extra["options"] == DETAILS["options"]
    assert run.submitted_at == datetime.fromisoformat(transport.reported["submitted_at"])


def test_a_job_already_archived_is_never_archived_twice(tmp_path: Path) -> None:
    transport = Submits()
    directory = submit(transport, plan(), tmp_path)
    # As if the process died after archiving and before removing its record.
    stale = tmp_path / ".pending-stale.json"
    stale.write_text(json.dumps({"job_id": "jobX", "backend": "b", "runs_dir": str(tmp_path)}))
    assert recover(NoFetch, "jobX", tmp_path) == directory
    assert not stale.exists()
    assert [p.name for p in tmp_path.iterdir()] == [directory.name]


def test_recovery_leaves_a_job_its_submitter_is_still_waiting_for(tmp_path: Path) -> None:
    import coin.hardware  # noqa: PLC0415 - the lock is the mechanism under test

    with pytest.raises(TimeoutError):
        submit(Submits(TimeoutError("queue")), plan(), tmp_path)
    (record,) = tmp_path.glob(".pending-*.json")
    # While a submitter holds the record's lock it is still waiting, whatever its pid.
    with coin.hardware._waiting(record), pytest.raises(ValueError, match="still being waited"):
        recover(Submits, "jobX", tmp_path)
    # The lock goes when the process does, and the job is then recoverable.
    assert recover(Submits, "jobX", tmp_path).name.endswith("jobX")


def test_one_unreadable_record_does_not_hide_the_others(tmp_path: Path) -> None:
    (tmp_path / ".pending-broken.json").write_text("")
    with pytest.raises(TimeoutError):
        submit(Submits(TimeoutError("queue")), plan(), tmp_path)
    found = pending_runs(tmp_path)
    assert sorted(p.problem is None for p in found) == [False, True]
    assert [p.record["job_id"] for p in found if p.record] == ["jobX"]


def test_a_record_kept_in_the_temp_directory_is_found_and_archived_here(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile  # noqa: PLC0415

    elsewhere = tmp_path / "tmp"
    elsewhere.mkdir()
    runs = tmp_path / "runs"
    with pytest.raises(TimeoutError):
        submit(Submits(TimeoutError("queue")), plan(), runs)
    (record,) = runs.glob(".pending-*.json")
    record.rename(elsewhere / record.name)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(elsewhere))
    run = recover(Submits, "jobX", runs)
    assert run.parent == runs
    assert not list(elsewhere.glob(".pending-*"))


def test_a_record_with_no_job_id_can_be_attached_or_discarded(tmp_path: Path) -> None:
    class LostId(FakeTransport):
        def run(self, *args: Any, **kwargs: Any) -> JobResult:
            error = ConnectionError("dropped before the id came back")
            setattr(error, "maybe_submitted", True)  # noqa: B010 - as IBMTransport does
            raise error

    with pytest.raises(ConnectionError) as caught:
        submit(LostId(("0",)), plan(), tmp_path)
    assert "IBM's dashboard" in "\n".join(caught.value.__notes__)
    (record,) = tmp_path.glob(".pending-*.json")
    run = load_run(recover(Submits, "jobX", tmp_path, record))
    assert run.job_id == "jobX"
    assert not list(tmp_path.glob(".pending-*"))

    with pytest.raises(ConnectionError):
        submit(LostId(("0",)), plan(), tmp_path)
    (record,) = tmp_path.glob(".pending-*.json")
    discard(record)
    assert not record.exists()


def test_an_interruption_while_archiving_keeps_the_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*_args: Any, **_kwargs: Any) -> Path:
        raise KeyboardInterrupt

    monkeypatch.setattr("coin.hardware.write_run", interrupted)
    with pytest.raises(KeyboardInterrupt) as caught:
        submit(Submits(), plan(), tmp_path)
    assert "coin recover jobX" in "\n".join(caught.value.__notes__)
    monkeypatch.undo()
    run = load_run(recover(NoFetch, "jobX", tmp_path))
    assert run.memory == ("0", "1", "1", "0")


@pytest.mark.parametrize("bad", ["*", "../x", "job x", ""])
def test_a_job_id_must_be_an_id(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="is not a job id"):
        recover(NoFetch, bad, tmp_path)


def lost_id_record(tmp_path: Path) -> Path:
    class LostId(FakeTransport):
        def run(self, *args: Any, **kwargs: Any) -> JobResult:
            error = ConnectionError("dropped before the id came back")
            setattr(error, "maybe_submitted", True)  # noqa: B010 - as IBMTransport does
            raise error

    with pytest.raises(ConnectionError):
        submit(LostId(("0",)), plan(), tmp_path)
    (record,) = tmp_path.glob(".pending-*.json")
    return record


def test_a_record_is_never_matched_to_a_job_already_archived(tmp_path: Path) -> None:
    submit(Submits(job_id="oldjob"), plan(), tmp_path)
    record = lost_id_record(tmp_path)
    with pytest.raises(ValueError, match="already archived"):
        recover(Submits, "oldjob", tmp_path, record)
    assert record.exists(), "the only copy of a prediction was deleted"


def test_a_record_that_names_one_job_is_not_archived_as_another(tmp_path: Path) -> None:
    with pytest.raises(TimeoutError):
        submit(Submits(TimeoutError("queue"), job_id="realjob"), plan(), tmp_path)
    (record,) = tmp_path.glob(".pending-*.json")
    with pytest.raises(ValueError, match="record for job realjob, not otherjob"):
        recover(Submits, "otherjob", tmp_path, record)
    assert record.exists()


def test_discard_keeps_a_record_that_names_a_job_unless_forced(tmp_path: Path) -> None:
    with pytest.raises(TimeoutError):
        submit(Submits(TimeoutError("queue")), plan(), tmp_path)
    (record,) = tmp_path.glob(".pending-*.json")
    with pytest.raises(ValueError, match="belongs to job jobX"):
        discard(record)
    assert record.exists()
    discard(record, force=True)
    assert not record.exists()


def test_discard_touches_only_pending_records(tmp_path: Path) -> None:
    notes = tmp_path / ".pending-notes.txt"
    notes.write_text("mine")
    with pytest.raises(ValueError, match="not a pending record"):
        discard(notes)
    assert notes.exists()


def test_the_runs_dir_given_decides_where_a_run_is_archived(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    with pytest.raises(TimeoutError):
        submit(Submits(TimeoutError("queue")), plan(), runs)
    (record,) = runs.glob(".pending-*.json")
    data = json.loads(record.read_text())
    record.write_text(json.dumps({**data, "runs_dir": str(tmp_path / "gone" / "runs")}))
    directory = recover(Submits, "jobX", runs)
    assert directory.parent == runs
    assert not (tmp_path / "gone").exists()


def test_losing_a_race_to_another_recovery_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import coin.hardware  # noqa: PLC0415

    with pytest.raises(TimeoutError):
        submit(Submits(TimeoutError("queue")), plan(), tmp_path)
    real = coin.hardware.write_run

    def other_recovery_wins(runs_dir: Path, run: Any, **kwargs: Any) -> Path:
        real(runs_dir, run, **kwargs)  # the other process's archive lands first
        raise ArchiveError("already exists")

    monkeypatch.setattr(coin.hardware, "write_run", other_recovery_wins)
    directory = recover(Submits, "jobX", tmp_path)
    assert directory.name.endswith("jobX")
    assert not list(tmp_path.glob(".pending-*"))
