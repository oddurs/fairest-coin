"""The one module that imports Qiskit: a `Transport` to IBM Quantum hardware.

Qiskit is transport here, not a foundation. Our own QASM goes in; Qiskit only maps it onto
the chosen physical qubits, and if mapping changes any gate the run is refused rather than
silently becoming a different experiment. Twirling and dynamical decoupling are switched off
explicitly, so a change of defaults can never alter what runs.

It uses SamplerV2, the path spike 0015 proved on hardware. SamplerV2 is deprecated in favour
of the client-side executor Sampler, whose result shape has not yet been seen on a real job;
moving is its own item, to be verified with a dry run before any QPU time depends on it.

Credentials come from QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE and are scrubbed from every
error this module raises. Install with the `ibm` extra.
"""

import json
import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from qiskit import qasm3, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

from coin.hardware import JobResult

TOKEN = "QISKIT_IBM_TOKEN"
INSTANCE = "QISKIT_IBM_INSTANCE"
CHANNEL = "ibm_quantum_platform"


class MissingCredentialsError(ValueError):
    """An IBM credential is not in the environment."""


class IBMError(RuntimeError):
    """Something failed talking to IBM; the message never contains a credential."""


class IBMTransport:
    """Submits to IBM Quantum through Qiskit Runtime."""

    def __init__(self, service_factory: Callable[[str, str], Any] | None = None) -> None:
        self._token = _require(TOKEN)
        self._instance = _require(INSTANCE)
        factory = service_factory or _service
        # Any: tests inject fakes, and Qiskit declares backends as BackendV2, which lacks the
        # IBM-specific properties() this module needs.
        self._service: Any = self._guard(lambda: factory(self._token, self._instance))

    def calibration(self, backend: str) -> dict[str, Any]:
        """The backend's current calibration as plain JSON (times and dates as strings)."""
        properties = self._guard(lambda: self._service.backend(backend).properties().to_dict())
        return json.loads(json.dumps(properties, default=str))

    def run(self, backend: str, qasm: str, layout: Sequence[int], shots: int) -> JobResult:
        target, isa, executed = self._guard(lambda: self._map(backend, qasm, layout))
        sampler = self._guard(lambda: sampler_for(target))
        options = _plain(sampler.options)
        submitted_at = datetime.now(UTC)
        job = self._guard(lambda: sampler.run([isa], shots=shots))
        # From here the QPU time is spent: every failure must name the job so it can be fetched.
        job_id = self._guard(job.job_id)
        return self._guard(
            lambda: self._collect(job, job_id, submitted_at, executed, options),
            job_id=job_id,
        )

    def _map(
        self, backend_name: str, qasm: str, layout: Sequence[int]
    ) -> tuple[Any, Any, dict[str, int]]:
        backend = self._service.backend(backend_name)
        circuit = qasm3.loads(qasm)
        isa = transpile(circuit, backend=backend, initial_layout=list(layout), optimization_level=0)
        # Mapping may only place each virtual qubit on its physical qubit. Routing inserts
        # swaps built from native gates, so comparing gate names would not catch it: compare
        # every instruction, its angles and its physical qubits, in order.
        expected = _instructions(circuit, list(layout))
        if _instructions(isa, list(range(isa.num_qubits))) != expected:
            raise IBMError("mapping changed the circuit (routing or rewriting); refusing to run it")
        return backend, isa, {name: int(count) for name, count in isa.count_ops().items()}

    def _collect(
        self,
        job: Any,
        job_id: str,
        submitted_at: datetime,
        executed: dict[str, int],
        options: dict[str, Any],
    ) -> JobResult:
        result = job.result()
        finished_at = datetime.now(UTC)
        memory = tuple(result[0].data.c.get_bitstrings())
        usage = job.metrics().get("usage")
        quantum = usage.get("quantum_seconds") if isinstance(usage, dict) else None
        return JobResult(
            job_id=job_id,
            submitted_at=submitted_at,
            finished_at=finished_at,
            memory=memory,
            quantum_seconds=quantum,
            usage=usage,
            executed_ops=executed,
            options=options,
        )

    def _guard[T](self, call: Callable[[], T], *, job_id: str | None = None) -> T:
        failure = ""
        try:
            return call()
        # Qiskit and its HTTP stack raise many unrelated types, and any of them may echo a
        # credential; translating them all here is the one place that can scrub it.
        except IBMError as error:
            failure = self._scrub(str(error))
        except Exception as error:
            failure = f"{type(error).__name__}: {self._scrub(str(error))}"
        if job_id is not None:
            failure = f"job {job_id} ran, but {failure}; fetch its result by that id"
        # Raised outside the except block so the unscrubbed error is neither the cause nor
        # the context of this one, and never prints in a chained traceback.
        raise IBMError(failure)

    def _scrub(self, text: str) -> str:
        return text.replace(self._token, f"<{TOKEN}>").replace(self._instance, f"<{INSTANCE}>")


# Off explicitly: either would change the circuit that actually runs on the qubits.
SAMPLER_OPTIONS: dict[str, Any] = {
    "twirling": {"enable_gates": False, "enable_measure": False},
    "dynamical_decoupling": {"enable": False},
}


def sampler_for(backend: Any) -> SamplerV2:
    """A sampler on `backend` that runs our circuit exactly as written."""
    return SamplerV2(mode=backend, options=SAMPLER_OPTIONS)


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise MissingCredentialsError(f"{name} is not set; export it before talking to IBM")
    return value


def _service(token: str, instance: str) -> QiskitRuntimeService:
    return QiskitRuntimeService(channel=CHANNEL, token=token, instance=instance)


def _plain(options: Any) -> dict[str, Any]:
    """Sampler options as plain JSON, for the archive."""

    # Qiskit marks options it leaves to the server with an empty sentinel; name it, so the
    # archive does not read as an empty setting.
    def encode(value: Any) -> Any:
        fields = getattr(value, "__dict__", None)
        return fields if fields else repr(value)

    return json.loads(json.dumps(options.__dict__, default=encode))


def _instructions(
    circuit: Any, physical: list[int]
) -> list[tuple[str, tuple[float, ...], tuple[int, ...]]]:
    """Each instruction as (name, angles, physical qubits); barriers carry no physics."""
    found = []
    for instruction in circuit.data:
        name = instruction.operation.name
        if name == "barrier":
            continue
        qubits = tuple(physical[circuit.find_bit(q).index] for q in instruction.qubits)
        angles = tuple(round(float(p), 12) for p in instruction.operation.params)
        found.append((name, angles, qubits))
    return found
