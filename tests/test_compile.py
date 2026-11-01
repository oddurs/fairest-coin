import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from qiskit import qasm3
from qiskit.quantum_info import Operator

from coin.circuit import ARITY, Circuit, Gate, Measure
from coin.compile import NATIVE, SNAP, lower, to_qasm
from coin.gates import matrix
from coin.sim import simulate

# Exact algebra, as in test_gates.py, for angles the lowering computes from a known gate.
EXACT = 1e-12

# Lowered against original. Merging and decomposing cost only rounding (atan2 and phase are
# accurate to the last bit; 20,000 random runs of up to 20 gates erred by at most 7e-15), but
# `lower` deliberately snaps to a shorter form when an angle is within SNAP of it, which moves
# an entry by up to SNAP/2. Up to three snaps per run plus rounding stay under 10·SNAP; a
# wrong decomposition misses by order 1.
LOWERED = 10 * SNAP

ONE_QUBIT = sorted(name for name, (k, _) in ARITY.items() if k == 1)
TWO_QUBIT = sorted(name for name, (k, _) in ARITY.items() if k == 2)
angles = st.floats(min_value=-4 * np.pi, max_value=4 * np.pi, allow_nan=False)


@st.composite
def one_qubit_gates(draw: st.DrawFn, q: int) -> Gate:
    name = draw(st.sampled_from(ONE_QUBIT))
    params = tuple(draw(angles) for _ in range(ARITY[name][1]))
    return Gate(name, (q,), params)


@st.composite
def gates(draw: st.DrawFn, n_qubits: int) -> Gate:
    names = ONE_QUBIT + (TWO_QUBIT if n_qubits > 1 else [])
    name = draw(st.sampled_from(names))
    k, n_params = ARITY[name]
    qubits = draw(st.permutations(range(n_qubits)))[:k]
    return Gate(name, tuple(qubits), tuple(draw(angles) for _ in range(n_params)))


@st.composite
def circuits(draw: st.DrawFn, max_qubits: int) -> Circuit:
    n = draw(st.integers(min_value=1, max_value=max_qubits))
    return Circuit(n, tuple(draw(st.lists(gates(n), max_size=20))))


def product(gate_list: list[Gate] | tuple[Gate, ...]) -> np.ndarray:
    u = np.eye(2, dtype=complex)
    for g in gate_list:
        u = matrix(g) @ u
    return u


def unitary(circuit: Circuit) -> np.ndarray:
    """The circuit as a 2ⁿ×2ⁿ matrix, column j simulated from basis state |j⟩."""
    n = circuit.n_qubits
    columns = []
    for j in range(2**n):
        prepare = tuple(Gate("x", (q,)) for q in range(n) if j >> q & 1)
        columns.append(simulate(Circuit(n, prepare + circuit.ops)))
    return np.stack(columns, axis=1)


def distance_up_to_phase(a: np.ndarray, b: np.ndarray) -> float:
    """Largest entry of a − e^{iφ}b, with φ the phase that best aligns b to a."""
    phase = np.exp(1j * np.angle(np.trace(b.conj().T @ a)))
    return float(np.max(np.abs(a - phase * b)))


def gate_names(circuit: Circuit) -> list[str]:
    return [op.name for op in circuit.ops if isinstance(op, Gate)]


@given(st.lists(one_qubit_gates(0), max_size=20))
def test_lowered_single_qubit_circuit_equals_the_original(gate_list: list[Gate]) -> None:
    lowered = lower(Circuit(1, tuple(gate_list)))
    ops = [op for op in lowered.ops if isinstance(op, Gate)]
    assert distance_up_to_phase(product(ops), product(gate_list)) < LOWERED


@given(circuits(max_qubits=3))
def test_lowered_circuit_equals_the_original(circuit: Circuit) -> None:
    assert distance_up_to_phase(unitary(lower(circuit)), unitary(circuit)) < LOWERED


@given(circuits(max_qubits=3))
def test_lowering_emits_only_native_gates_and_passes_two_qubit_gates_through(
    circuit: Circuit,
) -> None:
    lowered = lower(circuit)
    assert set(gate_names(lowered)) <= {"rz", "sx", "x", *TWO_QUBIT}
    two_qubit = [op for op in circuit.ops if isinstance(op, Gate) and op.name in TWO_QUBIT]
    assert [op for op in lowered.ops if isinstance(op, Gate) and op.name in TWO_QUBIT] == (
        two_qubit
    )


@given(st.lists(one_qubit_gates(0), max_size=20))
def test_a_run_lowers_to_at_most_two_sx_and_three_rz(gate_list: list[Gate]) -> None:
    names = gate_names(lower(Circuit(1, tuple(gate_list))))
    assert names.count("sx") <= 2
    assert names.count("rz") <= 3
    assert names.count("x") <= 1
    assert "x" not in names or names.count("sx") == 0


@given(st.lists(one_qubit_gates(0), max_size=20))
def test_every_rz_angle_is_normalised_and_not_the_identity(gate_list: list[Gate]) -> None:
    for op in lower(Circuit(1, tuple(gate_list))).ops:
        if isinstance(op, Gate) and op.name == "rz":
            assert -math.pi < op.params[0] <= math.pi
            assert abs(op.params[0]) >= SNAP


@pytest.mark.parametrize(
    ("circuit", "expected"),
    [
        (Circuit(1).rx(SNAP / 2, 0), []),
        (Circuit(1).rx(math.pi - SNAP / 2, 0), ["x"]),
        (Circuit(1).rx(math.pi / 2 + SNAP / 2, 0), ["sx"]),
        (Circuit(1).rx(2 * SNAP, 0), ["rz", "sx", "rz", "sx", "rz"]),
        (Circuit(1).rx(math.pi / 2 + 2 * SNAP, 0), ["rz", "sx", "rz", "sx", "rz"]),
    ],
    ids=["near-identity", "near-x", "near-sx", "past-identity", "past-sx"],
)
def test_snapping_takes_the_shorter_form_only_within_snap(
    circuit: Circuit, expected: list[str]
) -> None:
    lowered = lower(circuit)
    assert gate_names(lowered) == expected
    assert distance_up_to_phase(unitary(lowered), unitary(circuit)) < LOWERED


def assert_lowers_to(circuit: Circuit, expected: list[tuple[str, float | None]]) -> None:
    ops = lower(circuit).ops
    assert [op.name for op in ops if isinstance(op, Gate)] == [name for name, _ in expected]
    for op, (_, angle) in zip(ops, expected, strict=True):
        assert isinstance(op, Gate)
        if angle is not None:
            assert op.params[0] == pytest.approx(angle, abs=EXACT)


def test_hadamard_lowers_to_rz_sx_rz() -> None:
    assert_lowers_to(Circuit(1).h(0), [("rz", math.pi / 2), ("sx", None), ("rz", math.pi / 2)])


@pytest.mark.parametrize(
    ("circuit", "expected"),
    [
        (Circuit(1).z(0), [("rz", math.pi)]),
        (Circuit(1).s(0), [("rz", math.pi / 2)]),
        (Circuit(1).sdg(0), [("rz", -math.pi / 2)]),
        (Circuit(1).t(0), [("rz", math.pi / 4)]),
        (Circuit(1).rz(3 * math.pi, 0), [("rz", math.pi)]),
        (Circuit(1).x(0), [("x", None)]),
        (Circuit(1).rx(math.pi, 0), [("x", None)]),
        (Circuit(1).y(0), [("rz", math.pi), ("x", None)]),
        (Circuit(1).sx(0), [("sx", None)]),
    ],
    ids=["z", "s", "sdg", "t", "rz(3π)", "x", "rx(π)", "y", "sx"],
)
def test_known_gates_take_their_shortest_form(
    circuit: Circuit, expected: list[tuple[str, float | None]]
) -> None:
    assert_lowers_to(circuit, expected)


@pytest.mark.parametrize(
    "circuit",
    [Circuit(1), Circuit(1).i(0), Circuit(1).h(0).h(0), Circuit(1).rz(2 * math.pi, 0)],
    ids=["empty", "i", "hh", "rz(2π)"],
)
def test_identity_lowers_to_nothing(circuit: Circuit) -> None:
    assert lower(circuit).ops == ()


def test_gates_stay_on_their_side_of_two_qubit_gates_and_measurements() -> None:
    circuit = Circuit(2).h(0).x(1).cx(0, 1).z(0).cz(1, 0).h(1).measure_all()
    lowered = lower(circuit)
    names = [
        (op.name, op.qubits) if isinstance(op, Gate) else ("measure", (op.qubit,))
        for op in lowered.ops
    ]
    assert names == [
        ("rz", (0,)),
        ("sx", (0,)),
        ("rz", (0,)),
        ("x", (1,)),
        ("cx", (0, 1)),
        ("rz", (0,)),
        ("cz", (1, 0)),
        ("measure", (0,)),
        ("rz", (1,)),
        ("sx", (1,)),
        ("rz", (1,)),
        ("measure", (1,)),
    ]


def test_qasm_for_the_coin() -> None:
    assert to_qasm(lower(Circuit(1).h(0).measure(0, 0))) == (
        "OPENQASM 3.0;\n"
        'include "stdgates.inc";\n'
        "qubit[1] q;\n"
        "bit[1] c;\n"
        "rz(1.5707963267948966) q[0];\n"
        "sx q[0];\n"
        "rz(1.5707963267948966) q[0];\n"
        "c[0] = measure q[0];\n"
    )


@pytest.mark.parametrize("name", sorted(set(ARITY) - NATIVE))
def test_qasm_refuses_a_gate_outside_the_native_set(name: str) -> None:
    n_qubits, n_params = ARITY[name]
    circuit = Circuit(2).append(Gate(name, tuple(range(n_qubits)), (0.5,) * n_params))
    with pytest.raises(ValueError, match=f"^{name} is not a native gate"):
        to_qasm(circuit)


def test_qasm_keeps_every_digit_of_an_angle() -> None:
    angle = 0.1 + 0.2  # 0.30000000000000004: rounding to 15 digits would change it
    assert "rz(0.30000000000000004) q[0];" in to_qasm(Circuit(1).rz(angle, 0))


def native_only(circuit: Circuit) -> Circuit:
    # cx is not native and lowering two-qubit gates is 0037's job; cz conjugated by
    # Hadamards on the target is cx, so swapping it in keeps the circuit's meaning.
    ops = []
    for op in circuit.ops:
        if isinstance(op, Gate) and op.name == "cx":
            target = op.qubits[1]
            ops += [Gate("h", (target,)), Gate("cz", op.qubits), Gate("h", (target,))]
        else:
            ops.append(op)
    return Circuit(circuit.n_qubits, tuple(ops))


@given(circuits(max_qubits=3))
def test_qasm_parses_in_qiskit_to_the_same_unitary(circuit: Circuit) -> None:
    lowered = lower(native_only(circuit))
    parsed = qasm3.loads(to_qasm(lowered))
    assert parsed.num_qubits == circuit.n_qubits
    # Both use little-endian order, so the matrices compare with no qubit reversal.
    qiskit_unitary = np.asarray(Operator(parsed).data)
    assert distance_up_to_phase(qiskit_unitary, unitary(lowered)) < EXACT


def test_qasm_measurements_parse_to_the_right_bits() -> None:
    parsed = qasm3.loads(to_qasm(Circuit(2).measure(0, 1).measure(1, 0)))
    measured = [
        (parsed.find_bit(i.qubits[0]).index, parsed.find_bit(i.clbits[0]).index)
        for i in parsed.data
        if i.operation.name == "measure"
    ]
    assert measured == [(0, 1), (1, 0)]


def test_lower_keeps_measurements() -> None:
    assert lower(Circuit(1).measure(0, 0)).ops == (Measure(0, 0),)
