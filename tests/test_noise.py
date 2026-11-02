import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from coin.circuit import Circuit, Gate, Measure
from coin.gates import matrix
from coin.noise import (
    Readout,
    amplitude_damping,
    apply_readout,
    average_infidelity,
    coherent_bias_bound,
    depolarizing,
    gate_depolarizing,
    phase_damping,
    thermal_relaxation,
)
from coin.sim import Channel, probabilities, simulate_density

# Closed-form physics against exact simulation: anything above 1e-12 is a real mistake.
EXACT = 1e-12

unit = st.floats(min_value=0, max_value=1, allow_nan=False)


def on_gates(*channels: Channel):
    def noise(op: Gate | Measure) -> tuple[Channel, ...]:
        return channels if isinstance(op, Gate) else ()

    return noise


def complete(channel: Channel) -> bool:
    total = sum(k.conj().T @ k for k in channel.kraus)
    return np.allclose(total, np.eye(2), rtol=0, atol=EXACT)


@given(unit)
def test_every_channel_is_trace_preserving(x: float) -> None:
    for channel in (amplitude_damping(x, 0), phase_damping(x, 0), depolarizing(x, 0)):
        assert complete(channel)


@pytest.mark.parametrize("t", [0.0, 10.0, 50.0, 160.0, 500.0])
def test_amplitude_damping_matches_exponential_decay(t: float) -> None:
    t1 = 160.0
    gamma = 1 - math.exp(-t / t1)
    excited = Circuit(1).x(0).measure(0, 0)
    p1 = probabilities(excited, on_gates(amplitude_damping(gamma, 0))).get("1", 0.0)
    assert p1 == pytest.approx(math.exp(-t / t1), abs=EXACT)


@pytest.mark.parametrize(
    ("t1", "t2", "t"), [(160.0, 100.0, 30.0), (100.0, 200.0, 50.0), (80.0, 20.0, 5.0)]
)
def test_thermal_relaxation_decays_population_by_t1_and_coherence_by_t2(
    t1: float, t2: float, t: float
) -> None:
    # Start in |1⟩ for the population, and in |+⟩ for the coherence.
    excited = simulate_density(Circuit(1).x(0), on_gates(*thermal_relaxation(t1, t2, t, 0)))
    assert excited[1, 1].real == pytest.approx(math.exp(-t / t1), abs=EXACT)
    plus = simulate_density(Circuit(1).h(0), on_gates(*thermal_relaxation(t1, t2, t, 0)))
    assert abs(plus[0, 1]) == pytest.approx(0.5 * math.exp(-t / t2), abs=EXACT)


def test_thermal_relaxation_rejects_t2_beyond_twice_t1() -> None:
    with pytest.raises(ValueError, match="2·T1"):
        thermal_relaxation(100.0, 200.1, 10.0, 0)


@pytest.mark.parametrize(
    ("t1", "t2", "t"), [(0.0, 10.0, 1.0), (10.0, -1.0, 1.0), (10.0, 10.0, -1.0)]
)
def test_thermal_relaxation_rejects_nonsense_times(t1: float, t2: float, t: float) -> None:
    with pytest.raises(ValueError, match="need T1"):
        thermal_relaxation(t1, t2, t, 0)


def test_phase_damping_keeps_populations_and_shrinks_coherence() -> None:
    rho = simulate_density(Circuit(1).h(0), on_gates(phase_damping(0.36, 0)))
    assert rho[0, 0].real == pytest.approx(0.5, abs=EXACT)
    assert abs(rho[0, 1]) == pytest.approx(0.5 * math.sqrt(1 - 0.36), abs=EXACT)


@given(unit)
def test_depolarizing_mixes_towards_the_maximally_mixed_state(p: float) -> None:
    rho = simulate_density(Circuit(1).i(0), on_gates(depolarizing(p, 0)))
    expected = (1 - p) * np.diag([1, 0]) + p * np.eye(2) / 2
    assert np.allclose(rho, expected, rtol=0, atol=EXACT)


@pytest.mark.parametrize("make", [amplitude_damping, phase_damping, depolarizing])
@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_channels_reject_non_probabilities(make, bad: float) -> None:
    with pytest.raises(ValueError, match="probability"):
        make(bad, 0)


def test_readout_on_a_perfect_coin() -> None:
    reported = apply_readout({"0": 0.5, "1": 0.5}, {0: Readout(0.02, 0.05)})
    assert reported["1"] == pytest.approx(0.485, abs=EXACT)
    assert reported["0"] == pytest.approx(0.515, abs=EXACT)


def test_readout_errors_act_per_classical_bit() -> None:
    # True outcome '01': bit 0 is 1, bit 1 is 0. Only bit 0 is misread.
    reported = apply_readout({"01": 1.0}, {0: Readout(0.0, 0.1)})
    assert reported == pytest.approx({"01": 0.9, "00": 0.1}, abs=EXACT)
    both = apply_readout({"01": 1.0}, {0: Readout(0.0, 0.1), 1: Readout(0.2, 0.0)})
    assert both == pytest.approx(
        {"01": 0.9 * 0.8, "00": 0.1 * 0.8, "11": 0.9 * 0.2, "10": 0.1 * 0.2}, abs=EXACT
    )


@given(unit, unit, unit)
def test_readout_preserves_total_probability(p: float, e0: float, e1: float) -> None:
    reported = apply_readout({"0": p, "1": 1 - p}, {0: Readout(e0, e1)})
    assert sum(reported.values()) == pytest.approx(1.0, abs=EXACT)


def test_readout_rejects_bits_the_outcome_lacks() -> None:
    with pytest.raises(ValueError, match="classical bit 3"):
        apply_readout({"01": 1.0}, {3: Readout(0.1, 0.1)})


@pytest.mark.parametrize(("p10", "p01"), [(-0.01, 0.0), (0.0, 1.01)])
def test_readout_rejects_non_probabilities(p10: float, p01: float) -> None:
    with pytest.raises(ValueError, match="probability"):
        Readout(p10, p01)


def coin_with_error(error: Gate) -> Circuit:
    """The native coin with an unwanted rotation straight after its one physical gate."""
    return Circuit(1, (Gate("rz", (0,), (math.pi / 2,)), Gate("sx", (0,)), error)).measure(0, 0)


def infidelity(u: np.ndarray) -> float:
    """Average gate infidelity of a one-qubit unitary error, (2/3)·(1 − |Tr U / 2|²).

    Computed without cancellation: as V = U/√det U = [[a, −b*], [b, a*]], the bracket is
    Im(a)² + |b|². Subtracting from 1 would lose everything below 1e-16 to rounding.
    """
    v = u / np.sqrt(np.linalg.det(u))
    return 2 / 3 * (v[0, 0].imag ** 2 + abs(v[1, 0]) ** 2)


angle = st.floats(min_value=-math.pi / 2, max_value=math.pi / 2, allow_nan=False)


@given(angle)
def test_an_over_rotation_reaches_the_coherent_bound_exactly(epsilon: float) -> None:
    error = Gate("rx", (0,), (epsilon,))
    bias = probabilities(coin_with_error(error)).get("1", 0.0) - 0.5
    assert abs(bias) == pytest.approx(coherent_bias_bound(infidelity(matrix(error))), abs=EXACT)


@given(angle, angle, angle)
def test_no_unitary_error_of_that_size_biases_the_coin_further(
    a: float, b: float, c: float
) -> None:
    rotation = Circuit(1).rz(a, 0).ry(b, 0).rz(c, 0)
    u = np.eye(2, dtype=complex)
    for gate in rotation.ops:
        assert isinstance(gate, Gate)
        u = matrix(gate) @ u
    coin = Circuit(1, (Gate("rz", (0,), (math.pi / 2,)), Gate("sx", (0,)), *rotation.ops))
    bias = probabilities(coin.measure(0, 0)).get("1", 0.0) - 0.5
    assert abs(bias) <= coherent_bias_bound(min(infidelity(u), 2 / 3)) + EXACT


def test_the_bound_for_a_typical_heron_sx() -> None:
    # gate_error 2.5e-4 permits ε = 2·asin(√3.75e-4) ≈ 0.0387 rad: a bias of sin(ε)/2 ≈ ±1.94%.
    assert coherent_bias_bound(2.5e-4) == pytest.approx(0.0193613, abs=1e-7)
    assert coherent_bias_bound(0.0) == 0.0


@pytest.mark.parametrize("bad", [-1e-9, 0.67])
def test_the_bound_refuses_an_impossible_gate_error(bad: float) -> None:
    with pytest.raises(ValueError, match="2/3"):
        coherent_bias_bound(bad)


def test_average_infidelity_matches_closed_forms() -> None:
    assert average_infidelity(()) == pytest.approx(0.0, abs=EXACT)
    # Depolarizing at p: F_avg = 1 − p/2.
    assert average_infidelity((depolarizing(0.3, 0),)) == pytest.approx(0.15, abs=EXACT)
    # Amplitude damping at γ: F_e = (1 + √(1−γ))²/4.
    gamma = 0.2
    f_e = (1 + math.sqrt(1 - gamma)) ** 2 / 4
    expected = 1 - (2 * f_e + 1) / 3
    assert average_infidelity((amplitude_damping(gamma, 0),)) == pytest.approx(expected, abs=EXACT)


@given(
    st.floats(50_000, 400_000),
    st.floats(0.2, 1.0),
    st.floats(10, 200),
    st.floats(1e-5, 5e-3),
)
def test_relaxation_and_depolarizing_together_make_the_reported_error(
    t1: float, t2_fraction: float, length: float, gate_error: float
) -> None:
    relaxation = thermal_relaxation(t1, 2 * t1 * t2_fraction, length, 0)
    p = gate_depolarizing(gate_error, relaxation)
    total = average_infidelity((*relaxation, depolarizing(p, 0)))
    if average_infidelity(relaxation) < gate_error:
        # Not relaxation plus 2r on top: exactly the reported error, as IBM measured it.
        assert total == pytest.approx(gate_error, rel=1e-9)
    else:
        assert p == pytest.approx(0.0, abs=EXACT)


def test_relaxation_beyond_the_reported_error_leaves_no_depolarizing() -> None:
    # T1 = 10 µs over a 1 µs gate relaxes far more than a 1e-4 error allows.
    assert gate_depolarizing(1e-4, thermal_relaxation(10_000, 20_000, 1_000, 0)) == 0.0
