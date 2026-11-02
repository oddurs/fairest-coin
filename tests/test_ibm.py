import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

import pytest
from qiskit.providers.fake_provider import GenericBackendV2

from coin.circuit import Circuit
from coin.compile import to_qasm
from coin.ibm import IBMError, IBMTransport, MissingCredentialsError, sampler_for

TOKEN = "sentinel-token-1b2c3"
INSTANCE = "crn:v1:sentinel-instance"


@pytest.fixture
def credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QISKIT_IBM_TOKEN", TOKEN)
    monkeypatch.setenv("QISKIT_IBM_INSTANCE", INSTANCE)


class FakeService:
    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def backend(self, name: str) -> Any:
        return self._backend


class FakeProperties:
    def to_dict(self) -> dict[str, Any]:
        return {"backend_name": "fake", "last_update_date": datetime(2026, 11, 1, 22, 46)}


class FakeBackend:
    def properties(self) -> FakeProperties:
        return FakeProperties()


def test_importing_coin_never_needs_qiskit() -> None:
    # Block every Qiskit import, as on an install without the `ibm` extra.
    code = (
        "import sys\n"
        "for name in ('qiskit', 'qiskit_ibm_runtime', 'qiskit_qasm3_import'):\n"
        "    sys.modules[name] = None\n"
        "import coin, coin.cli, coin.hardware, coin.noise, coin.compile, coin.archive\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("missing", ["QISKIT_IBM_TOKEN", "QISKIT_IBM_INSTANCE"])
def test_a_missing_credential_is_named(
    missing: str, credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(missing)
    with pytest.raises(MissingCredentialsError, match=missing):
        IBMTransport(lambda _token, _instance: None)


def test_errors_never_carry_a_credential(credentials: None) -> None:
    def leaky(token: str, instance: str) -> Any:
        raise ConnectionError(f"login failed for token={token} on {instance}")

    with pytest.raises(IBMError) as caught:
        IBMTransport(leaky)
    message = str(caught.value)
    assert TOKEN not in message
    assert INSTANCE not in message
    assert "<QISKIT_IBM_TOKEN>" in message
    # Neither cause nor context: the unscrubbed original never prints in a chained traceback.
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_calibration_comes_back_as_plain_json(credentials: None) -> None:
    transport = IBMTransport(lambda _t, _i: FakeService(FakeBackend()))
    calibration = transport.calibration("fake")
    assert calibration == {"backend_name": "fake", "last_update_date": "2026-11-01 22:46:00"}


def test_a_circuit_that_mapping_would_change_is_refused(credentials: None) -> None:
    # This backend's two-qubit gate is ecr, so mapping must rewrite our cz: a different
    # experiment, which the transport refuses before anything is submitted.
    backend = GenericBackendV2(2, basis_gates=["ecr", "rz", "sx", "x"], seed=1)
    transport = IBMTransport(lambda _t, _i: FakeService(backend))
    qasm = to_qasm(Circuit(2).cz(0, 1).measure_all())
    with pytest.raises(IBMError, match="mapping changed the circuit"):
        transport.run("fake", qasm, [0, 1], 10)


# SamplerV2 is deprecated in favour of the executor Sampler; the warning is expected here.
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_the_sampler_runs_the_circuit_as_written() -> None:
    # Any: Qiskit types each option group as `Options | dict`; at runtime they are Options.
    options: Any = sampler_for(GenericBackendV2(1, basis_gates=["rz", "sx", "x"], seed=1)).options
    assert options.twirling.enable_gates is False
    assert options.twirling.enable_measure is False
    assert options.dynamical_decoupling.enable is False


NATIVE_COIN_QASM = to_qasm(
    Circuit(1).rz(1.5707963267948966, 0).sx(0).rz(1.5707963267948966, 0).measure(0, 0)
)
LINE = [[0, 1], [1, 0], [1, 2], [2, 1]]
# A local run warns that SamplerV2 is deprecated, that the sampler options do nothing without
# real hardware, and that it falls back to Qiskit's basic simulator; all expected offline.
LOCAL_RUN = (
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore:Options .* have no effect in local testing mode"),
    pytest.mark.filterwarnings("ignore:Aer not found"),
)


def heron_like(n: int) -> GenericBackendV2:
    return GenericBackendV2(
        n, basis_gates=["cz", "rz", "sx", "x"], coupling_map=LINE[: 2 * (n - 1)], seed=1
    )


@LOCAL_RUN[0]
@LOCAL_RUN[1]
@LOCAL_RUN[2]
def test_routing_is_refused_even_when_it_only_adds_native_gates(credentials: None) -> None:
    # cz between qubits 0 and 2 of a line needs swaps, which are built from native gates.
    transport = IBMTransport(lambda _t, _i: FakeService(heron_like(3)))
    qasm = to_qasm(Circuit(2).cz(0, 1).measure_all())
    with pytest.raises(IBMError, match="mapping changed the circuit"):
        transport.run("fake", qasm, [0, 2], 10)
    # On adjacent qubits the same circuit maps without change.
    assert transport.run("fake", qasm, [0, 1], 10).executed_ops["cz"] == 1


@LOCAL_RUN[0]
@LOCAL_RUN[1]
@LOCAL_RUN[2]
def test_a_run_comes_back_whole_from_a_local_backend(credentials: None) -> None:
    transport = IBMTransport(lambda _t, _i: FakeService(heron_like(2)))
    result = transport.run("fake", NATIVE_COIN_QASM, [1], 50)
    assert len(result.memory) == 50
    assert set(result.memory) <= {"0", "1"}
    assert result.executed_ops == {"rz": 2, "sx": 1, "measure": 1}
    assert result.options["twirling"]["enable_gates"] is False
    assert result.options["dynamical_decoupling"]["enable"] is False
    assert result.job_id


class FailingJob:
    def job_id(self) -> str:
        return "job-after-qpu-7"

    def result(self) -> Any:
        raise TimeoutError(f"lost connection; token {TOKEN}")


class FailingSampler:
    options = sampler_options = None

    def run(self, _pubs: Any, shots: int) -> FailingJob:
        return FailingJob()


def test_a_failure_after_submission_names_the_job(
    credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("coin.ibm.sampler_for", lambda _backend: FailingSampler())
    monkeypatch.setattr("coin.ibm._plain", lambda _options: {})
    transport = IBMTransport(lambda _t, _i: FakeService(heron_like(2)))
    with pytest.raises(IBMError) as caught:
        transport.run("fake", NATIVE_COIN_QASM, [0], 10)
    message = str(caught.value)
    assert "job-after-qpu-7" in message
    assert TOKEN not in message


class Bits:
    def __init__(self, memory: list[str]) -> None:
        self._memory = memory

    def get_bitstrings(self) -> list[str]:
        return self._memory


class Pub:
    def __init__(self, memory: list[str]) -> None:
        self.data = type("Data", (), {"c": Bits(memory)})()


class DoneJob:
    """A finished job whose usage call may fail, as an HTTP blip would make it."""

    def __init__(self, metrics: Any) -> None:
        self._metrics = metrics

    def job_id(self) -> str:
        return "job-done-1"

    def result(self) -> Any:
        return [Pub(["0", "1", "1"])]

    def metrics(self) -> Any:
        if isinstance(self._metrics, BaseException):
            raise self._metrics
        return self._metrics


class Sampler:
    options = sampler_options = None

    def __init__(self, job: Any) -> None:
        self._job = job

    def run(self, _pubs: Any, shots: int) -> Any:
        return self._job


def with_job(monkeypatch: pytest.MonkeyPatch, job: Any) -> IBMTransport:
    monkeypatch.setattr("coin.ibm.sampler_for", lambda _backend: Sampler(job))
    monkeypatch.setattr("coin.ibm._plain", lambda _options: {})
    return IBMTransport(lambda _t, _i: FakeService(heron_like(2)))


def test_a_usage_failure_keeps_the_shots(
    credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = with_job(monkeypatch, DoneJob(ConnectionError(f"blip {TOKEN}")))
    result = transport.run("fake", NATIVE_COIN_QASM, [0], 3)
    assert result.memory == ("0", "1", "1")
    assert (result.usage, result.quantum_seconds) == (None, None)


def test_qpu_seconds_come_from_the_usage_records_charge(
    credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The shape IBM returns: the charge is qpu_charge_time_seconds, even while pending.
    usage = {"qpu_charge_time_seconds": 8, "status": "pending", "unit": "resource_units"}
    transport = with_job(monkeypatch, DoneJob({"usage": usage}))
    result = transport.run("fake", NATIVE_COIN_QASM, [0], 3)
    assert result.quantum_seconds == pytest.approx(8.0)
    assert result.usage == usage


def test_an_interruption_while_waiting_carries_the_job_id(
    credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Interrupted(DoneJob):
        def result(self) -> Any:
            raise KeyboardInterrupt

    transport = with_job(monkeypatch, Interrupted({}))
    with pytest.raises(KeyboardInterrupt) as caught:
        transport.run("fake", NATIVE_COIN_QASM, [0], 3)
    assert getattr(caught.value, "job_id", None) == "job-done-1"


def test_a_failure_after_submission_carries_the_job_id(
    credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("coin.ibm.sampler_for", lambda _backend: FailingSampler())
    monkeypatch.setattr("coin.ibm._plain", lambda _options: {})
    transport = IBMTransport(lambda _t, _i: FakeService(heron_like(2)))
    with pytest.raises(IBMError) as caught:
        transport.run("fake", NATIVE_COIN_QASM, [0], 10)
    assert caught.value.job_id == "job-after-qpu-7"
    assert "coin recover job-after-qpu-7" in str(caught.value)


def test_a_finished_job_is_fetched_by_id(credentials: None) -> None:
    class Service(FakeService):
        def job(self, job_id: str) -> Any:
            assert job_id == "job-done-1"
            return DoneJob({"usage": {"qpu_charge_time_seconds": 5}})

    transport = IBMTransport(lambda _t, _i: Service(heron_like(2)))
    submitted = datetime.now(UTC)
    result = transport.fetch("fake", "job-done-1", submitted)
    assert (result.job_id, result.memory, result.submitted_at) == (
        "job-done-1",
        ("0", "1", "1"),
        submitted,
    )
    assert result.quantum_seconds == pytest.approx(5.0)


def test_the_adapter_reports_the_job_the_moment_it_exists(
    credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, dict[str, Any]]] = []
    transport = with_job(monkeypatch, DoneJob({}))
    transport.run(
        "fake", NATIVE_COIN_QASM, [0], 3, lambda job, details: seen.append((job, details))
    )
    ((job, details),) = seen
    assert job == "job-done-1"
    assert details["executed_ops"] == {"rz": 2, "sx": 1, "measure": 1}
    assert "submitted_at" in details


def test_bookkeeping_that_fails_does_not_abandon_the_job(
    credentials: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_job: str, _details: dict[str, Any]) -> None:
        raise OSError("disk full")

    transport = with_job(monkeypatch, DoneJob({}))
    result = transport.run("fake", NATIVE_COIN_QASM, [0], 3, broken)
    assert result.memory == ("0", "1", "1")


def test_a_failure_while_fetching_is_not_sent_back_to_recover(credentials: None) -> None:
    class Service(FakeService):
        def job(self, job_id: str) -> Any:
            raise LookupError(f"no such job {TOKEN}")

    transport = IBMTransport(lambda _t, _i: Service(heron_like(2)))
    with pytest.raises(IBMError) as caught:
        transport.fetch("fake", "gone-1", datetime.now(UTC))
    message = str(caught.value)
    assert message.startswith("fetching job gone-1")
    assert "coin recover" not in message
    assert TOKEN not in message
