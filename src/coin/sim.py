"""The ideal coin: exact statevector simulation, and shots drawn by the Born rule.

A state of n qubits is a vector of 2ⁿ complex amplitudes. Basis index i holds qubit q in bit
q of i (little-endian, as in Qiskit), so the outcome string of a measurement reads with
qubit 0, or classical bit 0, on the right.

Gates are applied by viewing the vector as an n-axis tensor and contracting the gate with
just the axes it touches, which never builds a 2ⁿ×2ⁿ matrix. Measurement must be terminal:
once a qubit is measured, no gate may touch it again.
"""

from collections.abc import Iterator

import numpy as np
import numpy.typing as npt

from coin.circuit import Circuit, Gate, Measure
from coin.gates import matrix

type StateVector = npt.NDArray[np.complex128]

# Below this a probability is rounding error, not an outcome: rx(π) leaves ~1e-33 on |0⟩.
NEGLIGIBLE = 1e-12


def simulate(circuit: Circuit) -> StateVector:
    """The state after every gate in `circuit`, starting from |0…0⟩. Measurements are skipped."""
    n = circuit.n_qubits
    state = np.zeros((2,) * n, dtype=np.complex128)
    state[(0,) * n] = 1
    for gate in _gates(circuit):
        state = _apply(state, gate, n)
    return state.reshape(2**n)


def probabilities(circuit: Circuit) -> dict[str, float]:
    """Exact probability of each classical outcome string.

    Outcomes below `NEGLIGIBLE` are omitted, so the keys are the outcomes that can happen.
    """
    readout = _readout(circuit)
    born = _born(simulate(circuit))
    totals: dict[str, float] = {}
    for index in np.flatnonzero(born):
        key = _outcome(int(index), readout, circuit.n_qubits)
        totals[key] = totals.get(key, 0.0) + float(born[index])
    # Filter after summing: an outcome can be many basis states, each too small alone.
    return {key: p for key, p in totals.items() if p > NEGLIGIBLE}


def sample(circuit: Circuit, shots: int, rng: np.random.Generator) -> dict[str, int]:
    """Run `circuit` `shots` times and count the classical outcome strings.

    The generator is required, never global, so every sample in the project can be replayed.
    """
    if shots < 1:
        raise ValueError(f"shots must be at least 1, got {shots}")
    readout = _readout(circuit)
    counts = rng.multinomial(shots, _born(simulate(circuit)))
    result: dict[str, int] = {}
    for index in np.flatnonzero(counts):
        key = _outcome(int(index), readout, circuit.n_qubits)
        result[key] = result.get(key, 0) + int(counts[index])
    return result


def _gates(circuit: Circuit) -> Iterator[Gate]:
    measured: set[int] = set()
    for op in circuit.ops:
        if isinstance(op, Measure):
            measured.add(op.qubit)
            continue
        if touched := measured.intersection(op.qubits):
            raise ValueError(
                f"{op.name} acts on qubit {min(touched)} after it was measured; "
                "the simulator supports terminal measurement only"
            )
        yield op


def _apply(state: npt.NDArray[np.complex128], gate: Gate, n: int) -> npt.NDArray[np.complex128]:
    k = len(gate.qubits)
    # The gate's matrix is ordered |q_{k-1} … q_0⟩ (first-listed qubit least significant),
    # and qubit q sits on tensor axis n-1-q, so both lists run most significant first.
    unitary = matrix(gate).reshape((2,) * (2 * k))
    axes = [n - 1 - q for q in reversed(gate.qubits)]
    contracted = np.tensordot(unitary, state, axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(contracted, list(range(k)), axes)


def _born(state: StateVector) -> npt.NDArray[np.float64]:
    born = np.abs(state) ** 2
    # Renormalise away rounding drift so multinomial sees probabilities that sum to 1.
    return born / born.sum()


def _readout(circuit: Circuit) -> dict[int, int]:
    """Classical bit → the qubit last measured into it."""
    readout = {op.clbit: op.qubit for op in circuit.ops if isinstance(op, Measure)}
    if not readout:
        raise ValueError("the circuit measures nothing, so it has no outcomes")
    return readout


def _outcome(index: int, readout: dict[int, int], n: int) -> str:
    """The classical bit string recorded when the qubits are found in basis state `index`.

    Built only for basis states that occur, never for all 2ⁿ of them.
    """
    bits = ["0"] * n  # unmeasured classical bits read 0, as on hardware
    for clbit, qubit in readout.items():
        bits[n - 1 - clbit] = str((index >> qubit) & 1)
    return "".join(bits)
