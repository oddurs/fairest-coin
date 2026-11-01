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

from coin.compile import NATIVE
from coin.hardware import JobResult

TOKEN = "QISKIT_IBM_TOKEN"
INSTANCE = "QISKIT_IBM_INSTANCE"
CHANNEL = "ibm_quantum_platform"
# Mapping onto physical qubits may add these; anything else means Qiskit changed the circuit.
_ALLOWED_AFTER_MAPPING = NATIVE | {"measure", "barrier"}


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
        return self._guard(lambda: self._run(backend, qasm, layout, shots))

    def _run(self, backend_name: str, qasm: str, layout: Sequence[int], shots: int) -> JobResult:
        backend = self._service.backend(backend_name)
        isa = transpile(
            qasm3.loads(qasm), backend=backend, initial_layout=list(layout), optimization_level=0
        )
        executed = {name: int(count) for name, count in isa.count_ops().items()}
        if changed := set(executed) - _ALLOWED_AFTER_MAPPING:
            raise IBMError(
                f"mapping introduced {sorted(changed)}; refusing to run a changed circuit"
            )

        sampler = sampler_for(backend)
        options = _plain(sampler.options)

        submitted_at = datetime.now(UTC)
        job = sampler.run([isa], shots=shots)
        result = job.result()
        finished_at = datetime.now(UTC)
        try:
            memory = tuple(result[0].data.c.get_bitstrings())
        except AttributeError as error:
            # The job ran and its QPU time is spent; say how to recover the result.
            raise IBMError(
                f"job {job.job_id()} finished but its result was unreadable: {error}"
            ) from None
        usage = job.metrics().get("usage")
        quantum = usage.get("quantum_seconds") if isinstance(usage, dict) else None
        return JobResult(
            job_id=job.job_id(),
            submitted_at=submitted_at,
            finished_at=finished_at,
            memory=memory,
            quantum_seconds=quantum,
            usage=usage,
            executed_ops=executed,
            options=options,
        )

    def _guard[T](self, call: Callable[[], T]) -> T:
        try:
            return call()
        except IBMError as error:
            raise IBMError(self._scrub(str(error))) from None
        # Qiskit and its HTTP stack raise many unrelated types, and any of them may echo a
        # credential; translating them all here is the one place that can scrub it.
        except Exception as error:
            raise IBMError(f"{type(error).__name__}: {self._scrub(str(error))}") from None

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
