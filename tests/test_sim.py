import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from coin.circuit import ARITY, Circuit, Gate
from coin.gates import matrix
from coin.sim import probabilities, sample, simulate

# Exact algebra: anything above rounding error is a real mistake.
EXACT = 1e-10

COIN = Circuit(1).h(0).measure(0, 0)
BELL = Circuit(2).h(0).cx(0, 1).measure_all()


@st.composite
def gates(draw: st.DrawFn, n_qubits: int) -> Gate:
    names = [name for name, (k, _) in ARITY.items() if k <= n_qubits]
    name = draw(st.sampled_from(sorted(names)))
    k, n_params = ARITY[name]
    qubits = draw(st.permutations(range(n_qubits)))[:k]
    angle = st.floats(min_value=-2 * np.pi, max_value=2 * np.pi, allow_nan=False)
    params = tuple(draw(angle) for _ in range(n_params))
    return Gate(name, tuple(qubits), params)


@st.composite
def circuits(draw: st.DrawFn, max_qubits: int) -> Circuit:
    n = draw(st.integers(min_value=1, max_value=max_qubits))
    ops = draw(st.lists(gates(n), max_size=20))
    return Circuit(n, tuple(ops))


def reference_unitary(circuit: Circuit) -> np.ndarray:
    """The whole circuit as an explicit 2ⁿ×2ⁿ matrix, built by bit indexing.

    Independent of the simulator's tensor contraction: each gate's full matrix is filled in
    entry by entry from the bits of the basis indices it connects.
    """
    n = circuit.n_qubits
    total = np.eye(2**n, dtype=complex)
    for op in circuit.ops:
        assert isinstance(op, Gate)
        u = matrix(op)
        full = np.zeros((2**n, 2**n), dtype=complex)
        rest_mask = ~sum(1 << q for q in op.qubits)
        for col in range(2**n):
            sub_in = sum(((col >> q) & 1) << i for i, q in enumerate(op.qubits))
            for sub_out in range(2 ** len(op.qubits)):
                row = col & rest_mask
                for i, q in enumerate(op.qubits):
                    row |= ((sub_out >> i) & 1) << q
                full[row, col] = u[sub_out, sub_in]
        total = full @ total
    return total


def test_coin_is_fifty_fifty() -> None:
    assert probabilities(COIN) == pytest.approx({"0": 0.5, "1": 0.5}, abs=EXACT)


def test_bell_pair_always_agrees() -> None:
    assert probabilities(BELL) == pytest.approx({"00": 0.5, "11": 0.5}, abs=EXACT)


def test_qubit_zero_is_the_rightmost_bit() -> None:
    assert probabilities(Circuit(3).x(0).measure_all()) == {"001": 1.0}
    assert probabilities(Circuit(3).x(2).measure_all()) == {"100": 1.0}


def test_classical_bit_mapping_is_honoured() -> None:
    # qubit 0 into classical bit 1: the 1 appears in the second position from the right
    assert probabilities(Circuit(2).x(0).measure(0, 1)) == {"10": 1.0}


def test_two_qubits_into_one_classical_bit_keeps_the_last() -> None:
    # As on hardware, a later measurement overwrites the classical bit.
    assert probabilities(Circuit(3).x(0).measure(0, 0).measure(1, 0)) == {"000": 1.0}
    assert probabilities(Circuit(3).x(1).measure(0, 0).measure(1, 0)) == {"001": 1.0}


def test_one_qubit_into_two_classical_bits_fills_both() -> None:
    assert probabilities(Circuit(3).x(0).measure(0, 0).measure(0, 2)) == {"101": 1.0}


def test_rounding_error_is_not_an_outcome() -> None:
    assert set(probabilities(Circuit(1).rx(np.pi, 0).measure(0, 0))) == {"1"}


def test_unmeasured_classical_bits_read_zero() -> None:
    assert probabilities(Circuit(2).x(0).x(1).measure(0, 0)) == {"01": 1.0}


def test_initial_state_is_all_zeros() -> None:
    state = simulate(Circuit(3))
    assert state[0] == 1
    assert np.count_nonzero(state) == 1


@settings(max_examples=200)
@given(circuits(max_qubits=6))
def test_norm_is_preserved(circuit: Circuit) -> None:
    assert abs(np.linalg.norm(simulate(circuit)) - 1) < EXACT


@settings(max_examples=200)
@given(circuits(max_qubits=3))
def test_contraction_agrees_with_explicit_matrix(circuit: Circuit) -> None:
    expected = reference_unitary(circuit)[:, 0]
    assert np.allclose(simulate(circuit), expected, rtol=0, atol=EXACT)


def test_same_seed_same_samples() -> None:
    first = sample(COIN, 999, np.random.default_rng(7))
    second = sample(COIN, 999, np.random.default_rng(7))
    assert first == second
    # Pinned from a real run: a change here means the sampling procedure changed.
    assert first == {"0": 500, "1": 499}


def test_ten_thousand_flips_land_near_half() -> None:
    shots = 10_000
    counts = sample(COIN, shots, np.random.default_rng(2026))
    sigma = np.sqrt(shots * 0.5 * 0.5)
    assert abs(counts["0"] - shots / 2) < 3 * sigma
    assert counts["0"] + counts["1"] == shots


def test_bell_samples_never_disagree() -> None:
    counts = sample(BELL, 5_000, np.random.default_rng(1))
    assert set(counts) == {"00", "11"}


def test_gate_after_measurement_is_rejected() -> None:
    with pytest.raises(ValueError, match="after it was measured"):
        simulate(Circuit(1).measure(0, 0).h(0))


def test_gates_on_other_qubits_after_a_measurement_are_fine() -> None:
    assert probabilities(Circuit(2).measure(0, 0).x(1).measure(1, 1)) == {"10": 1.0}


def test_circuit_without_measurement_has_no_outcomes() -> None:
    with pytest.raises(ValueError, match="measures nothing"):
        probabilities(Circuit(1).h(0))


@pytest.mark.parametrize("shots", [0, -5])
def test_shots_must_be_positive(shots: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        sample(COIN, shots, np.random.default_rng(0))
