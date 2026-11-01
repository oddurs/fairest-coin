import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from coin.circuit import Circuit, Gate, Measure
from coin.noise import (
    Readout,
    amplitude_damping,
    apply_readout,
    depolarizing,
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
