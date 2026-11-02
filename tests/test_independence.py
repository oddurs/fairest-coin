"""The statistics behind spike 0028, checked on synthetic bits whose answer is known.

A test of independence is only evidence if it stays quiet on independent bits and speaks
up on dependent ones, so each check here runs both ways. Seeds are fixed; the thresholds
are wide enough that the seeded draws sit far inside them.
"""

import importlib.util
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from coin.archive import Prediction, Run

spec = importlib.util.spec_from_file_location(
    "independence", Path(__file__).parent.parent / "analysis" / "independence.py"
)
assert spec is not None
assert spec.loader is not None
independence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(independence)

SHOTS = 20_000


def biased(p: float, shots: int, columns: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).random((shots, columns)) < p


def markov(stay: float, shots: int, seed: int) -> np.ndarray:
    """A fair coin that repeats its last outcome with probability `stay`, else flips fresh."""
    rng = np.random.default_rng(seed)
    x = np.empty(shots, dtype=bool)
    x[0] = rng.random() < 0.5
    fresh = rng.random(shots) < 0.5
    keep = rng.random(shots) < stay
    for t in range(1, shots):
        x[t] = x[t - 1] if keep[t] else fresh[t]
    return x


def p_values(x: np.ndarray, block: int | None) -> np.ndarray:
    r = independence.autocorrelation(independence.centred(x, block))
    q = independence.ljung_box(r, len(x))
    return np.array([independence.chi2_sf(float(v), independence.MAX_LAG) for v in q])


@pytest.mark.parametrize(
    ("q", "p"),
    # Upper χ² quantiles for 100 degrees of freedom, from standard tables.
    [(124.342, 0.05), (135.807, 0.01), (149.449, 0.001), (100.0, 0.4757)],
)
def test_the_chi_square_tail_matches_the_tables(q: float, p: float) -> None:
    assert independence.chi2_sf(q, 100) == pytest.approx(p, rel=0.03)


def test_independent_biased_coins_pass_the_memory_test_at_the_nominal_rate() -> None:
    # 60 coins at 70% tails: with p uniform under independence, about 0.6 fall below 0.01.
    p = p_values(biased(0.7, SHOTS, 60, seed=1), block=None)
    assert np.sum(p < 0.01) <= 3
    assert 0.3 < np.median(p) < 0.7


def test_strong_shot_to_shot_memory_fails_ljung_box() -> None:
    # Repeating the last outcome 10% of the time is r_1 = 0.1: Q ≈ 100 + n·r_1² = 300.
    x = np.column_stack([markov(0.1, SHOTS, seed=2), biased(0.5, SHOTS, 1, seed=3)[:, 0]])
    p = p_values(x, block=None)
    assert p[0] < 1e-6
    assert p[1] > 0.01


@pytest.mark.parametrize("seed", range(5))
def test_weak_memory_needs_the_lag_one_test(seed: int) -> None:
    # r_1 = 0.05 is 7σ at lag 1, but spread over 100 lags Ljung-Box gives only Q ≈ 150,
    # which is why the analysis reports lag 1 on its own as well.
    x = markov(0.05, SHOTS, seed=10 + seed)[:, None]
    r = independence.autocorrelation(independence.centred(x, None))
    assert r[0, 0] * math.sqrt(SHOTS) > 4


def test_blocks_remove_slow_drift_but_keep_fast_memory() -> None:
    # A coin drifting from 40% to 60% tails across the run correlates with itself at every
    # lag; within 5,000-shot blocks the drift is nearly flat and the coin looks independent.
    rng = np.random.default_rng(4)
    drifting = rng.random(SHOTS) < np.linspace(0.4, 0.6, SHOTS)
    x = np.column_stack([drifting, markov(0.1, SHOTS, seed=5)])
    raw, blocked = p_values(x, block=None), p_values(x, block=independence.BLOCK)
    assert raw[0] < 1e-6
    assert blocked[0] > 0.01
    assert blocked[1] < 1e-6


def test_same_shot_correlation_is_found_only_where_it_exists() -> None:
    x = biased(0.5, SHOTS, 3, seed=6)
    # Qubit 1 copies qubit 0 in 5% of shots: a correlation of about 0.05, about 7σ.
    copy = np.random.default_rng(7).random(SHOTS) < 0.05
    x[copy, 1] = x[copy, 0]
    z = independence.pair_correlation(independence.centred(x, None), [(0, 1), (0, 2)])
    z *= math.sqrt(SHOTS)
    assert z[0] > 5
    assert abs(z[1]) < 3


def test_von_neumann_makes_independent_biased_coins_fair() -> None:
    fraction, count = independence.von_neumann(biased(0.8, SHOTS, 40, seed=8))
    z = (fraction - 0.5) * 2 * np.sqrt(count)
    assert np.all(np.abs(z) < 4)
    # Each pair gives a bit with probability 2·0.8·0.2 = 0.32: about 3,200 from 10,000 pairs.
    assert np.all(np.abs(count - 3200) < 4 * math.sqrt(10_000 * 0.32 * 0.68))


def test_von_neumann_is_fooled_by_a_coin_that_drifts_within_pairs() -> None:
    # The second shot of every pair leans more to tails than the first: 10 is likelier than
    # 01, so the "fair" output is biased toward 1. Independence is the assumption it needs.
    rng = np.random.default_rng(9)
    p = np.where(np.arange(SHOTS) % 2 == 0, 0.6, 0.4)[:, None]
    fraction, count = independence.von_neumann(rng.random((SHOTS, 1)) < p)
    assert (fraction[0] - 0.5) * 2 * math.sqrt(count[0]) > 5


def test_bits_put_classical_bit_zero_in_column_zero() -> None:
    now = datetime.now(UTC)
    run = Run(
        job_id="j",
        backend="b",
        qubits=(5, 9),
        shots=2,
        submitted_at=now,
        finished_at=now,
        circuit_qasm="",
        counts={"01": 1, "10": 1},
        calibration={},
        prediction=Prediction(now - timedelta(seconds=1), {}),
        memory=("01", "10"),
    )
    assert independence.bits(run).tolist() == [[True, False], [False, True]]


def test_a_periodic_disturbance_shows_as_one_line_and_white_noise_does_not() -> None:
    # A 5% oscillation in P(tails) at 0.489 cycles per shot, the kind that aliases near
    # Nyquist when something periodic is sampled at the shot rate. Its expected peak is
    # A²·n = 50 times the mean power, so white noise matches it with p ≈ 10⁴·e⁻⁵⁰.
    t = np.arange(SHOTS)
    rng = np.random.default_rng(11)
    wobbly = rng.random(SHOTS) < 0.5 + 0.05 * np.cos(2 * np.pi * 0.489 * t)
    frequency, _, chance = independence.spectral_peak(wobbly)
    assert frequency == pytest.approx(0.489, abs=1 / SHOTS)
    assert chance < 1e-6
    _, _, chance = independence.spectral_peak(biased(0.5, SHOTS, 1, seed=12)[:, 0])
    assert chance > 0.01
