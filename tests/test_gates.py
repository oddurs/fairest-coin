from collections.abc import Callable

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from qiskit import QuantumCircuit
from qiskit.circuit import Gate as QiskitGate
from qiskit.circuit import library
from qiskit.quantum_info import Operator

from coin import gates
from coin.circuit import ARITY, Gate
from coin.gates import CX, CZ, SX, H, I, S, X, Z, matrix, rx, ry, rz

# Exact algebra on unit-modulus entries: anything above rounding error is a real mistake.
EXACT = 1e-12

angles = st.floats(min_value=-4 * np.pi, max_value=4 * np.pi, allow_nan=False)


def close(a: np.ndarray, b: np.ndarray) -> bool:
    return np.allclose(a, b, rtol=0, atol=EXACT)


def equal_up_to_phase(a: np.ndarray, b: np.ndarray) -> bool:
    # |tr(A†B)| equals the dimension exactly when B = e^{iφ}A for unitaries A, B.
    return abs(abs(np.trace(a.conj().T @ b)) - a.shape[0]) < EXACT


def is_unitary(m: np.ndarray) -> bool:
    return close(m.conj().T @ m, np.eye(m.shape[0]))


@pytest.mark.parametrize("name", sorted(ARITY))
def test_every_gate_is_a_unitary_of_the_right_size(name: str) -> None:
    n_qubits, n_params = ARITY[name]
    m = matrix(Gate(name, tuple(range(n_qubits)), (0.7,) * n_params))
    assert m.shape == (2**n_qubits, 2**n_qubits)
    assert is_unitary(m)


@given(angles)
def test_rotations_are_unitary_at_any_angle(theta: float) -> None:
    for rotation in (rx, ry, rz):
        assert is_unitary(rotation(theta))


@given(angles, angles)
def test_rotations_compose_by_adding_angles(a: float, b: float) -> None:
    for rotation in (rx, ry, rz):
        assert close(rotation(a) @ rotation(b), rotation(a + b))


@pytest.mark.parametrize(
    ("lhs", "rhs"),
    [
        (H @ H, I),
        (S @ S, Z),
        (SX @ SX, X),
        (H @ Z @ H, X),
        (H @ X @ H, Z),
        (gates.T @ gates.T, S),
        (S @ gates.SDG, I),
    ],
    ids=["HH=I", "SS=Z", "SXSX=X", "HZH=X", "HXH=Z", "TT=S", "S·Sdg=I"],
)
def test_identities(lhs: np.ndarray, rhs: np.ndarray) -> None:
    assert close(lhs, rhs)


def test_rz_follows_qiskit_convention() -> None:
    theta = 0.3
    assert close(rz(theta), np.diag([np.exp(-1j * theta / 2), np.exp(1j * theta / 2)]))
    assert close(rz(np.pi), -1j * Z)


def test_sx_is_a_half_x_rotation_up_to_phase() -> None:
    assert equal_up_to_phase(SX, rx(np.pi / 2))
    assert close(SX, np.exp(1j * np.pi / 4) * rx(np.pi / 2))


def test_cx_control_is_the_first_qubit_and_least_significant() -> None:
    # Gate("cx", (0, 1)): control qubit 0, target qubit 1, basis |q1 q0⟩.
    basis = np.eye(4)
    assert close(CX @ basis[0b01], basis[0b11])  # control set: target flips
    assert close(CX @ basis[0b10], basis[0b10])  # control clear: nothing happens
    assert close(CX @ basis[0b11], basis[0b01])


def test_cx_is_cz_conjugated_by_hadamards_on_the_target() -> None:
    h_on_target = np.kron(H, I)  # target is qubit b, the more significant factor
    assert close(CX, h_on_target @ CZ @ h_on_target)


def test_shared_matrices_cannot_be_mutated() -> None:
    with pytest.raises(ValueError, match="read-only"):
        H[0, 0] = 0
    with pytest.raises(ValueError, match="read-only"):
        rz(0.1)[0, 0] = 0


# Written out independently of coin.gates, from Qiskit's published definitions, so a wrong
# matrix or a wrong name → matrix mapping in coin.gates cannot also be wrong here.
_P0 = np.array([[1, 0], [0, 0]])
_P1 = np.array([[0, 0], [0, 1]])
_PAULI_X = np.array([[0, 1], [1, 0]])
_PAULI_Y = np.array([[0, -1j], [1j, 0]])
_PAULI_Z = np.array([[1, 0], [0, -1]])
_EYE = np.eye(2)

REFERENCE = {
    "i": _EYE,
    "x": _PAULI_X,
    "y": _PAULI_Y,
    "z": _PAULI_Z,
    "h": np.array([[1, 1], [1, -1]]) / np.sqrt(2),
    "s": np.diag([1, 1j]),
    "sdg": np.diag([1, -1j]),
    "t": np.diag([1, (1 + 1j) / np.sqrt(2)]),
    "sx": np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]]) / 2,
    # Little-endian, first qubit is control: |0⟩⟨0| on the control, or X / Z on the target.
    "cx": np.kron(_EYE, _P0) + np.kron(_PAULI_X, _P1),
    "cz": np.kron(_EYE, _P0) + np.kron(_PAULI_Z, _P1),
}
ROTATION_AXES = {"rx": _PAULI_X, "ry": _PAULI_Y, "rz": _PAULI_Z}


def test_reference_covers_every_gate() -> None:
    assert set(REFERENCE) | set(ROTATION_AXES) == set(ARITY)


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_matrix_matches_reference_exactly(name: str) -> None:
    n_qubits, _ = ARITY[name]
    assert close(matrix(Gate(name, tuple(range(n_qubits)))), REFERENCE[name])


@pytest.mark.parametrize("name", sorted(ROTATION_AXES))
@given(theta=angles)
def test_rotation_is_exp_of_its_pauli(name: str, theta: float) -> None:
    # exp(-iθσ/2) = cos(θ/2)·I − i·sin(θ/2)·σ, since σ² = I.
    sigma = ROTATION_AXES[name]
    expected = np.cos(theta / 2) * _EYE - 1j * np.sin(theta / 2) * sigma
    assert close(matrix(Gate(name, (0,), (theta,))), expected)


@pytest.mark.parametrize("name", sorted(ROTATION_AXES))
def test_half_turn_rotation_is_its_pauli_up_to_minus_i(name: str) -> None:
    assert close(matrix(Gate(name, (0,), (np.pi,))), -1j * ROTATION_AXES[name])


# Qiskit's own gate classes, by our name: a second, independent source for every matrix.
QISKIT: dict[str, Callable[..., QiskitGate]] = {
    "i": library.IGate,
    "x": library.XGate,
    "y": library.YGate,
    "z": library.ZGate,
    "h": library.HGate,
    "s": library.SGate,
    "sdg": library.SdgGate,
    "t": library.TGate,
    "sx": library.SXGate,
    "rx": library.RXGate,
    "ry": library.RYGate,
    "rz": library.RZGate,
    "cx": library.CXGate,
    "cz": library.CZGate,
}


def test_qiskit_mapping_covers_every_gate() -> None:
    assert set(QISKIT) == set(ARITY)


@pytest.mark.parametrize("name", sorted(QISKIT))
def test_matrix_matches_qiskit_exactly(name: str) -> None:
    n_qubits, n_params = ARITY[name]
    params = (0.7,) * n_params
    ours = matrix(Gate(name, tuple(range(n_qubits)), params))
    assert close(ours, np.asarray(Operator(QISKIT[name](*params)).data))


@pytest.mark.parametrize("name", sorted(n for n, (k, _) in ARITY.items() if k == 2))
@pytest.mark.parametrize("qubits", [(0, 1), (1, 0)])
def test_two_qubit_order_matches_a_qiskit_circuit(name: str, qubits: tuple[int, int]) -> None:
    # Our matrix acts on |q_b q_a⟩ for qubits (a, b); a Qiskit circuit's operator always acts
    # on |q1 q0⟩. They agree as they stand for (0, 1), and up to a swap of the two factors
    # for (1, 0); a big-endian slip in either library would break one of the two.
    circuit = QuantumCircuit(2)
    circuit.append(QISKIT[name](), list(qubits))
    swap = np.eye(4)[[0, 2, 1, 3]]
    ours = matrix(Gate(name, qubits))
    expected = ours if qubits == (0, 1) else swap @ ours @ swap
    assert close(np.asarray(Operator(circuit).data), expected)
