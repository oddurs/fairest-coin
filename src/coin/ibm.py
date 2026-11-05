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

import contextlib
import json
import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, quote_plus

from qiskit import qasm3, transpile
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.executor_sampler import Sampler

from coin.hardware import JobResult

TOKEN = "QISKIT_IBM_TOKEN"
INSTANCE = "QISKIT_IBM_INSTANCE"
CHANNEL = "ibm_quantum_platform"


class MissingCredentialsError(ValueError):
    """An IBM credential is not in the environment."""


class IBMError(RuntimeError):
    """Something failed talking to IBM; the message never contains a credential.

    `job_id` is set when the failure came after IBM accepted the job: the QPU time is spent,
    and the job can still be fetched by that id.
    """

    def __init__(self, message: str, job_id: str | None = None) -> None:
        super().__init__(message)
        self.job_id = job_id


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

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> JobResult:
        target, isa, executed = self._guard(lambda: self._map(backend, qasm, layout))
        sampler = self._guard(lambda: sampler_for(target))
        options = _plain(sampler.options)
        submitted_at = datetime.now(UTC)
        try:
            job = self._guard(lambda: sampler.run([isa], shots=shots))
            job_id = self._guard(job.job_id)
        except BaseException as error:
            # The job may already be on the hardware without its id reaching us.
            setattr(error, "maybe_submitted", True)  # noqa: B010 - not declared on BaseException
            raise
        # From here the QPU time is spent: every failure must carry the job id so it can be
        # fetched, including an interruption (Ctrl-C while waiting in the queue).
        try:
            if on_submitted is not None:
                details = {
                    "submitted_at": submitted_at.isoformat(),
                    "executed_ops": executed,
                    "options": options,
                }
                # Best effort: the caller's bookkeeping must never abandon a job in the queue,
                # and the result (or the error) still carries the job id.
                with contextlib.suppress(Exception):
                    on_submitted(job_id, details)
            return self._guard(
                lambda: self._collect(job, job_id, submitted_at, executed, options),
                job_id=job_id,
            )
        except BaseException as error:
            if getattr(error, "job_id", None) is None:
                setattr(error, "job_id", job_id)  # noqa: B010 - BaseException declares no job_id
            raise

    def fetch(self, backend: str, job_id: str, submitted_at: datetime) -> JobResult:
        """A finished job's result, by id: for a run whose waiting was cut short.

        What ran (the gate counts and the sampler options) is known only at submission; the
        pending record keeps them, and `hardware.recover` fills them in.
        """
        try:
            job = self._guard(lambda: self._service.job(job_id))
            return self._guard(lambda: self._collect(job, job_id, submitted_at, {}, {}))
        except IBMError as error:
            # Not "job ran, recover it": this is the recovery, and the job may have failed.
            raise IBMError(f"fetching job {job_id}: {error}") from None

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
        # The shots are in hand; the usage is a separate call, and losing it must not lose them.
        usage = self._usage(job)
        quantum = None
        if usage is not None:
            charged = usage.get("qpu_charge_time_seconds", usage.get("quantum_seconds"))
            quantum = float(charged) if isinstance(charged, int | float) else None
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

    def _usage(self, job: Any) -> dict[str, Any] | None:
        """The job's usage record, or None if it cannot be read now (IBM keeps it)."""
        try:
            usage = job.metrics().get("usage")
        # As in _guard, any of Qiskit's error types may arrive; here none of them is fatal.
        except Exception:
            return None
        return usage if isinstance(usage, dict) else None

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
            failure = f"job {job_id} ran, but {failure}; `coin recover {job_id}` fetches it"
        # Raised outside the except block so the unscrubbed error is neither the cause nor
        # the context of this one, and never prints in a chained traceback.
        raise IBMError(failure, job_id=job_id)

    def _scrub(self, text: str) -> str:
        # An error can echo a credential as it appeared in a URL: percent-encoded once or
        # twice, or form-encoded. The instance CRN holds ':' and '/', so it is rarely verbatim.
        for secret, name in ((self._token, TOKEN), (self._instance, INSTANCE)):
            for form in sorted(_encodings(secret), key=len, reverse=True):
                text = text.replace(form, f"<{name}>")
        return text


# Off explicitly: either would change the circuit that actually runs on the qubits.
SAMPLER_OPTIONS: dict[str, Any] = {
    "twirling": {"enable_gates": False, "enable_measure": False},
    "dynamical_decoupling": {"enable": False},
}


def sampler_for(backend: Any) -> Sampler:
    """A sampler on `backend` that runs our circuit exactly as written.

    The executor Sampler, which replaced the deprecated SamplerV2: it post-processes results
    on the client into the same PrimitiveResult shape, so the shots are read as before.
    """
    return Sampler(mode=backend, options=SAMPLER_OPTIONS)


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


def _encodings(secret: str) -> set[str]:
    """The forms a secret takes in URLs and their echoes: verbatim, percent-encoded once and
    twice (either case of hex digit), and form-encoded."""
    once = quote(secret, safe="")
    forms = {secret, once, quote(once, safe=""), quote_plus(secret)}
    return forms | {form.lower() for form in forms if "%" in form}


def _instructions(
    circuit: Any, physical: list[int]
) -> list[tuple[str, tuple[float, ...], tuple[int, ...], tuple[int, ...]]]:
    """Each instruction as (name, angles, physical qubits, classical bits).

    Barriers carry no physics. The classical bits matter: a measurement that landed in
    another bit would put one qubit's outcome under another's name.
    """
    found = []
    for instruction in circuit.data:
        name = instruction.operation.name
        if name == "barrier":
            continue
        qubits = tuple(physical[circuit.find_bit(q).index] for q in instruction.qubits)
        clbits = tuple(circuit.find_bit(c).index for c in instruction.clbits)
        angles = tuple(round(float(p), 12) for p in instruction.operation.params)
        found.append((name, angles, qubits, clbits))
    return found
