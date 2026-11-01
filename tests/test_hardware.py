import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from coin.archive import Prediction, load_run
from coin.circuit import Circuit
from coin.hardware import JobResult, Submission, submit

NATIVE_COIN = Circuit(1).rz(math.pi / 2, 0).sx(0).rz(math.pi / 2, 0).measure(0, 0)
CALIBRATION: dict[str, Any] = {"qubits": [], "gates": [], "backend_name": "fake_backend"}


class FakeTransport:
    """Returns a fixed result and records every submission, with no network."""

    def __init__(self, memory: tuple[str, ...]) -> None:
        self.memory = memory
        self.submitted: list[tuple[str, str, list[int], int]] = []

    def calibration(self, backend: str) -> dict[str, Any]:
        return CALIBRATION

    def run(self, backend: str, qasm: str, layout: Sequence[int], shots: int) -> JobResult:
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


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"prediction": prediction(datetime.now(UTC) + timedelta(hours=1))}, "before submission"),
        ({"prediction": prediction(datetime(2026, 1, 1))}, "timezone"),
        ({"circuit": Circuit(1).h(0).measure(0, 0)}, "h"),
        ({"layout": (1, 2)}, "distinct qubits"),
        ({"circuit": Circuit(2).measure_all(), "layout": (5, 5)}, "distinct qubits"),
        ({"shots": 0}, "at least 1"),
    ],
)
def test_bad_submissions_are_refused_before_reaching_hardware(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    transport = FakeTransport(("0",))
    with pytest.raises(ValueError, match=message):
        go(transport, tmp_path, **changes)
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
