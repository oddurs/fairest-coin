"""Circuits as immutable values: what to do to which qubits, never how to do it.

The simulator, the noise model, the compiler and the QASM emitter all read this one
description, so it holds no execution logic of its own.
"""

import math
from dataclasses import dataclass
from numbers import Integral, Real

# Every gate the project knows: name → (number of qubits, number of parameters).
ARITY: dict[str, tuple[int, int]] = {
    "i": (1, 0),
    "x": (1, 0),
    "y": (1, 0),
    "z": (1, 0),
    "h": (1, 0),
    "s": (1, 0),
    "sdg": (1, 0),
    "t": (1, 0),
    "sx": (1, 0),
    "rx": (1, 1),
    "ry": (1, 1),
    "rz": (1, 1),
    "cx": (2, 0),
    "cz": (2, 0),
}


@dataclass(frozen=True)
class Gate:
    """A named gate on specific qubits. For two-qubit gates the first qubit is the control."""

    name: str
    qubits: tuple[int, ...]
    params: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in ARITY:
            raise ValueError(f"unknown gate {self.name!r}")
        n_qubits, n_params = ARITY[self.name]
        if len(self.qubits) != n_qubits:
            raise ValueError(f"{self.name} acts on {n_qubits} qubit(s), got {len(self.qubits)}")
        if len(self.params) != n_params:
            raise ValueError(f"{self.name} takes {n_params} parameter(s), got {len(self.params)}")
        if len(set(self.qubits)) != len(self.qubits):
            raise ValueError(f"{self.name} acts on qubit {self.qubits[0]} more than once")
        for q in self.qubits:
            _require_index(f"{self.name} qubit", q)
        for theta in self.params:
            # A NaN angle would poison the whole state and every probability after it.
            if not isinstance(theta, Real) or not math.isfinite(theta):
                raise ValueError(f"{self.name} needs a finite angle, got {theta!r}")


@dataclass(frozen=True)
class Measure:
    """Measure a qubit in the computational basis into a classical bit."""

    qubit: int
    clbit: int


type Op = Gate | Measure


@dataclass(frozen=True)
class Circuit:
    """An ordered sequence of operations on `n_qubits` qubits and as many classical bits.

    Builder methods return a new circuit and leave this one unchanged:
    `Circuit(1).h(0).measure(0, 0)` is the coin.
    """

    n_qubits: int
    ops: tuple[Op, ...] = ()

    def __post_init__(self) -> None:
        _require_index("qubit count", self.n_qubits)
        if self.n_qubits < 1:
            raise ValueError(f"a circuit needs at least one qubit, got {self.n_qubits}")
        for op in self.ops:
            qubits = op.qubits if isinstance(op, Gate) else (op.qubit,)
            for q in qubits:
                self._check_index("qubit", q)
            if isinstance(op, Measure):
                self._check_index("classical bit", op.clbit)

    def _check_index(self, kind: str, index: int) -> None:
        _require_index(kind, index)
        if not 0 <= index < self.n_qubits:
            raise ValueError(f"{kind} {index} is outside a {self.n_qubits}-qubit circuit")

    def append(self, op: Op) -> "Circuit":
        return Circuit(self.n_qubits, (*self.ops, op))

    def gate(self, name: str, *qubits: int, params: tuple[float, ...] = ()) -> "Circuit":
        return self.append(Gate(name, qubits, params))

    def measure(self, qubit: int, clbit: int) -> "Circuit":
        return self.append(Measure(qubit, clbit))

    def measure_all(self) -> "Circuit":
        circuit = self
        for q in range(self.n_qubits):
            circuit = circuit.measure(q, q)
        return circuit

    def i(self, q: int) -> "Circuit":
        return self.gate("i", q)

    def x(self, q: int) -> "Circuit":
        return self.gate("x", q)

    def y(self, q: int) -> "Circuit":
        return self.gate("y", q)

    def z(self, q: int) -> "Circuit":
        return self.gate("z", q)

    def h(self, q: int) -> "Circuit":
        return self.gate("h", q)

    def s(self, q: int) -> "Circuit":
        return self.gate("s", q)

    def sdg(self, q: int) -> "Circuit":
        return self.gate("sdg", q)

    def t(self, q: int) -> "Circuit":
        return self.gate("t", q)

    def sx(self, q: int) -> "Circuit":
        return self.gate("sx", q)

    def rx(self, theta: float, q: int) -> "Circuit":
        return self.gate("rx", q, params=(theta,))

    def ry(self, theta: float, q: int) -> "Circuit":
        return self.gate("ry", q, params=(theta,))

    def rz(self, theta: float, q: int) -> "Circuit":
        return self.gate("rz", q, params=(theta,))

    def cx(self, control: int, target: int) -> "Circuit":
        return self.gate("cx", control, target)

    def cz(self, a: int, b: int) -> "Circuit":
        return self.gate("cz", a, b)


def _require_index(kind: str, value: object) -> None:
    # 1.0 passes a range check and then breaks array indexing; True is an int to Python.
    if not isinstance(value, Integral) or isinstance(value, bool):
        raise ValueError(f"{kind} must be an integer, got {value!r}")
