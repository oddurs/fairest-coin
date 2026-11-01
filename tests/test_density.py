import time
from collections.abc import Callable

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from coin.circuit import Circuit, Gate, Measure
from coin.gates import CX as CX_MATRIX
from coin.sim import Channel, probabilities, sample, simulate, simulate_density
from tests.strategies import circuits

# Exact algebra, as in test_sim.py: anything above 1e-12 is a real mistake.
EXACT = 1e-12
# Eigenvalues of a valid ρ are ≥ 0; rounding over a 20-gate noisy circuit stays well inside this.
PSD_SLACK = 1e-10


def random_channel(rng: np.random.Generator, qubits: tuple[int, ...], n_kraus: int) -> Channel:
    """A random valid channel: Kraus operators cut from a random isometry V, so Σ K†K = V†V = I."""
    d = 2 ** len(qubits)
    a = rng.normal(size=(d * n_kraus, d)) + 1j * rng.normal(size=(d * n_kraus, d))
    v, _ = np.linalg.qr(a)
    return Channel(tuple(v[i * d : (i + 1) * d] for i in range(n_kraus)), qubits)


def noise_from(seed: int) -> Callable[[Gate | Measure], list[Channel]]:
    rng = np.random.default_rng(seed)

    def noise(op: Gate | Measure) -> list[Channel]:
        qubits = op.qubits if isinstance(op, Gate) else (op.qubit,)
        return [random_channel(rng, qubits, int(rng.integers(1, 4)))]

    return noise


def assert_valid_density(rho: np.ndarray) -> None:
    assert np.allclose(rho, rho.conj().T, rtol=0, atol=EXACT), "rho is not Hermitian"
    assert abs(np.trace(rho).real - 1) < EXACT, "trace of rho is not 1"
    assert np.linalg.eigvalsh(rho).min() > -PSD_SLACK, "rho has a negative eigenvalue"


@settings(max_examples=200)
@given(circuits(max_qubits=5))
def test_noiseless_density_is_the_pure_state(circuit: Circuit) -> None:
    psi = simulate(circuit)
    assert np.allclose(simulate_density(circuit), np.outer(psi, psi.conj()), rtol=0, atol=EXACT)


@settings(max_examples=100)
@given(circuits(max_qubits=4), st.integers(min_value=0, max_value=2**32 - 1))
def test_density_stays_valid_under_random_channels(circuit: Circuit, seed: int) -> None:
    rho = simulate_density(circuit.measure_all(), noise_from(seed))
    assert_valid_density(rho)


def test_noise_that_adds_nothing_changes_nothing() -> None:
    bell = Circuit(2).h(0).cx(0, 1).measure_all()
    assert probabilities(bell, noise=lambda _op: []) == pytest.approx(
        probabilities(bell), abs=EXACT
    )


def test_full_dephasing_kills_interference() -> None:
    # H·H returns heads only through interference. Dephase in between and the coin is random.
    dephase = Channel((np.diag([1, 0]).astype(complex), np.diag([0, 1]).astype(complex)), (0,))
    twice = Circuit(1).h(0).h(0).measure(0, 0)
    noise_after_first_h = iter([[dephase], [], []])
    result = probabilities(twice, noise=lambda _op: next(noise_after_first_h))
    assert result == pytest.approx({"0": 0.5, "1": 0.5}, abs=EXACT)
    assert probabilities(twice) == pytest.approx({"0": 1.0}, abs=EXACT)


def test_channel_on_one_qubit_of_two_respects_qubit_order() -> None:
    # Reset qubit 1 to |0⟩ (K0 = |0⟩⟨0|, K1 = |0⟩⟨1|) after X on both: qubit 0 keeps its 1.
    reset = Channel(
        (np.array([[1, 0], [0, 0]], complex), np.array([[0, 1], [0, 0]], complex)), (1,)
    )
    circuit = Circuit(2).x(0).x(1).measure_all()
    gates_seen: list[str] = []

    def noise(op: Gate | Measure) -> list[Channel]:
        if isinstance(op, Gate):
            gates_seen.append(op.name)
            return [reset] if len(gates_seen) == 2 else []
        return []

    assert probabilities(circuit, noise) == pytest.approx({"01": 1.0}, abs=EXACT)


def test_noisy_sampling_replays_with_the_same_seed() -> None:
    coin = Circuit(1).h(0).measure(0, 0)
    flip_half = Channel(
        (
            np.sqrt(0.5) * np.eye(2, dtype=complex),
            np.sqrt(0.5) * np.array([[0, 1], [1, 0]], complex),
        ),
        (0,),
    )

    def noise(_op: Gate | Measure) -> list[Channel]:
        return [flip_half]

    first = sample(coin, 999, np.random.default_rng(5), noise)
    assert first == sample(coin, 999, np.random.default_rng(5), noise)
    assert sum(first.values()) == 999


@pytest.mark.parametrize(
    ("kraus", "qubits", "message"),
    [
        ((), (0,), "at least one"),
        ((np.eye(4, dtype=complex),), (0,), "Kraus operator of shape"),
        ((0.5 * np.eye(2, dtype=complex),), (0,), "not complete"),
    ],
)
def test_invalid_channels_are_rejected(
    kraus: tuple[np.ndarray, ...], qubits: tuple[int, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Channel(kraus, qubits)


def test_five_qubit_noisy_circuit_runs_within_a_second() -> None:
    circuit = Circuit(5)
    for layer in range(4):
        for q in range(5):
            circuit = circuit.ry(0.3 * (layer + q), q)
        for q in range(4):
            circuit = circuit.cx(q, q + 1)
    circuit = circuit.measure_all()
    noise = noise_from(0)
    start = time.perf_counter()
    simulate_density(circuit, noise)
    assert time.perf_counter() - start < 1.0


BIT_FLIP = np.array([[0, 1], [1, 0]], dtype=complex)


def test_a_measurements_channels_act_before_readout() -> None:
    flip = Channel((BIT_FLIP,), (0,))
    result = probabilities(
        Circuit(1).measure(0, 0), noise=lambda op: [flip] if isinstance(op, Measure) else []
    )
    assert result == pytest.approx({"1": 1.0}, abs=EXACT)


def test_two_qubit_channel_orientation_follows_its_qubit_order() -> None:
    # A CX-shaped channel on (1, 0): qubit 1 controls, qubit 0 is flipped.
    cx_channel = Channel((np.array(CX_MATRIX, dtype=complex),), (1, 0))
    circuit = Circuit(2).x(1).measure_all()
    result = probabilities(circuit, noise=lambda op: [cx_channel] if isinstance(op, Gate) else [])
    assert result == pytest.approx({"11": 1.0}, abs=EXACT)


@pytest.mark.parametrize("qubits", [(2,), (5,), (-1,)])
def test_channel_on_a_qubit_outside_the_circuit_is_rejected(qubits: tuple[int, ...]) -> None:
    stray = Channel((BIT_FLIP,), qubits)
    with pytest.raises(ValueError, match="outside"):
        simulate_density(Circuit(2).x(0), noise=lambda _op: [stray])


def test_channel_with_a_repeated_qubit_is_rejected() -> None:
    with pytest.raises(ValueError, match="more than once"):
        Channel((np.eye(4, dtype=complex),), (1, 1))


def test_noise_on_an_already_measured_qubit_is_rejected() -> None:
    # Qubit 0 was read as 0; noise from the later X on qubit 1 must not rewrite that answer.
    flip_q0 = Channel((BIT_FLIP,), (0,))
    circuit = Circuit(2).measure(0, 0).x(1).measure(1, 1)
    with pytest.raises(ValueError, match="after it was measured"):
        probabilities(circuit, noise=lambda op: [flip_q0] if isinstance(op, Gate) else [])
