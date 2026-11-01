"""The ideal coin: exact statevector simulation, and shots drawn by the Born rule.

A state of n qubits is a vector of 2ⁿ complex amplitudes. Basis index i holds qubit q in bit
q of i (little-endian, as in Qiskit), so the outcome string of a measurement reads with
qubit 0, or classical bit 0, on the right.

Gates are applied by viewing the vector as an n-axis tensor and contracting the gate with
just the axes it touches, which never builds a 2ⁿ×2ⁿ matrix. Measurement must be terminal:
once a qubit is measured, no gate may touch it again.

Noise turns a pure state into a mixture, which a statevector cannot hold. With a `noise`
model the simulator switches to a density matrix ρ, a 2n-axis tensor: a gate U acts as UρU†
and a channel with Kraus operators Kᵢ as Σ KᵢρKᵢ†. The diagonal of ρ gives the outcome
probabilities.
"""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from coin.circuit import Circuit, Gate, Measure
from coin.gates import matrix

type StateVector = npt.NDArray[np.complex128]
type DensityMatrix = npt.NDArray[np.complex128]
type Matrix = npt.NDArray[np.complex128]

# Σ K†K must equal I; anything beyond rounding means the channel creates or loses probability.
COMPLETENESS = 1e-10

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


@dataclass(frozen=True)
class Channel:
    """A quantum channel on `qubits`, given by Kraus operators in the gates' qubit order."""

    kraus: tuple[Matrix, ...]
    qubits: tuple[int, ...]

    def __post_init__(self) -> None:
        dim = 2 ** len(self.qubits)
        if len(set(self.qubits)) != len(self.qubits):
            raise ValueError(f"a channel acts on qubit {self.qubits[0]} more than once")
        if not self.kraus:
            raise ValueError("a channel needs at least one Kraus operator")
        for k in self.kraus:
            if k.shape != (dim, dim):
                raise ValueError(
                    f"Kraus operator of shape {k.shape} on {len(self.qubits)} qubit(s)"
                )
        total = sum(k.conj().T @ k for k in self.kraus)
        if not np.allclose(total, np.eye(dim), rtol=0, atol=COMPLETENESS):
            raise ValueError("Kraus operators are not complete: Σ K†K ≠ I")


# Channels to apply after each operation. For a Measure they act just before readout, which
# is where decay during the measurement window belongs.
type Noise = Callable[[Gate | Measure], Iterable[Channel]]


def simulate_density(circuit: Circuit, noise: Noise | None = None) -> DensityMatrix:
    """ρ after every operation in `circuit`, from |0…0⟩⟨0…0|, as a 2ⁿ×2ⁿ matrix."""
    n = circuit.n_qubits
    rho = np.zeros((2,) * (2 * n), dtype=np.complex128)
    rho[(0,) * (2 * n)] = 1
    measured: set[int] = set()
    for op in _ops(circuit):
        if isinstance(op, Gate):
            u = matrix(op)
            rho = _conjugate(rho, u, op.qubits, n)
        for channel in noise(op) if noise else ():
            _check_channel_qubits(channel, n, measured)
            rho = sum(
                (_conjugate(rho, k, channel.qubits, n) for k in channel.kraus),
                start=np.zeros_like(rho),
            )
        if isinstance(op, Measure):
            # A measurement's own channels act before readout; afterwards the qubit is read.
            measured.add(op.qubit)
    return rho.reshape(2**n, 2**n)


def _check_channel_qubits(channel: Channel, n: int, measured: set[int]) -> None:
    for q in channel.qubits:
        # numpy would wrap a stray index onto another axis and act on the wrong qubit.
        if not 0 <= q < n:
            raise ValueError(f"channel qubit {q} is outside a {n}-qubit circuit")
        if q in measured:
            raise ValueError(
                f"noise acts on qubit {q} after it was measured; "
                "the simulator supports terminal measurement only"
            )


def probabilities(circuit: Circuit, noise: Noise | None = None) -> dict[str, float]:
    """Exact probability of each classical outcome string, with `noise` if given.

    Outcomes below `NEGLIGIBLE` are omitted, so the keys are the outcomes that can happen.
    """
    readout = _readout(circuit)
    born = _distribution(circuit, noise)
    totals: dict[str, float] = {}
    for index in np.flatnonzero(born):
        key = _outcome(int(index), readout, circuit.n_qubits)
        totals[key] = totals.get(key, 0.0) + float(born[index])
    # Filter after summing: an outcome can be many basis states, each too small alone.
    return {key: p for key, p in totals.items() if p > NEGLIGIBLE}


def sample(
    circuit: Circuit, shots: int, rng: np.random.Generator, noise: Noise | None = None
) -> dict[str, int]:
    """Run `circuit` `shots` times and count the classical outcome strings.

    The generator is required, never global, so every sample in the project can be replayed.
    """
    if shots < 1:
        raise ValueError(f"shots must be at least 1, got {shots}")
    readout = _readout(circuit)
    counts = rng.multinomial(shots, _distribution(circuit, noise))
    result: dict[str, int] = {}
    for index in np.flatnonzero(counts):
        key = _outcome(int(index), readout, circuit.n_qubits)
        result[key] = result.get(key, 0) + int(counts[index])
    return result


def _ops(circuit: Circuit) -> Iterator[Gate | Measure]:
    measured: set[int] = set()
    for op in circuit.ops:
        if isinstance(op, Measure):
            measured.add(op.qubit)
        elif touched := measured.intersection(op.qubits):
            raise ValueError(
                f"{op.name} acts on qubit {min(touched)} after it was measured; "
                "the simulator supports terminal measurement only"
            )
        yield op


def _gates(circuit: Circuit) -> Iterator[Gate]:
    return (op for op in _ops(circuit) if isinstance(op, Gate))


def _apply(state: npt.NDArray[np.complex128], gate: Gate, n: int) -> npt.NDArray[np.complex128]:
    k = len(gate.qubits)
    # The gate's matrix is ordered |q_{k-1} … q_0⟩ (first-listed qubit least significant),
    # and qubit q sits on tensor axis n-1-q, so both lists run most significant first.
    unitary = matrix(gate).reshape((2,) * (2 * k))
    axes = [n - 1 - q for q in reversed(gate.qubits)]
    contracted = np.tensordot(unitary, state, axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(contracted, list(range(k)), axes)


def _conjugate(
    rho: npt.NDArray[np.complex128], op: Matrix, qubits: tuple[int, ...], n: int
) -> npt.NDArray[np.complex128]:
    """op·ρ·op† on the given qubits of a 2n-axis density tensor."""
    k = len(qubits)
    t = op.reshape((2,) * (2 * k))
    rows = [n - 1 - q for q in reversed(qubits)]
    cols = [2 * n - 1 - q for q in reversed(qubits)]
    # (ρ op†)_{ij} = Σ_m ρ_{im} conj(op_{jm}): the column side contracts with conj(op).
    for axes, factor in ((rows, t), (cols, t.conj())):
        rho = np.tensordot(factor, rho, axes=(list(range(k, 2 * k)), axes))
        rho = np.moveaxis(rho, list(range(k)), axes)
    return rho


def _distribution(circuit: Circuit, noise: Noise | None) -> npt.NDArray[np.float64]:
    """Probability of each basis state: the Born rule, or the diagonal of ρ under noise."""
    if noise is None:
        return _born(simulate(circuit))
    diagonal = np.clip(np.diagonal(simulate_density(circuit, noise)).real, 0, None)
    return diagonal / diagonal.sum()


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
