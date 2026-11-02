import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from coin.extract import as_bits, peres, von_neumann

MILLION = 1_000_000

# Biases a real qubit could plausibly have, and well beyond.
bias = st.floats(min_value=0.05, max_value=0.95)
seed = st.integers(min_value=0, max_value=2**32 - 1)


def coin(p: float, n: int, seed: int) -> np.ndarray:
    return (np.random.default_rng(seed).random(n) < p).astype(np.uint8)


def z_fair(bits: np.ndarray) -> float:
    """How many σ the fraction of ones is from ½."""
    return (bits.mean() - 0.5) / (0.5 / math.sqrt(len(bits)))


def test_von_neumann_keeps_01_as_0_and_10_as_1() -> None:
    #                pairs: 01 10 00 11 10, and an odd last bit
    assert von_neumann([0, 1, 1, 0, 0, 0, 1, 1, 1, 0, 1]).tolist() == [0, 1, 1]


def test_peres_by_hand() -> None:
    # Pairs 00 11 01: von Neumann gives [0]. u = 0 0 1 has one full pair, 00, which gives
    # nothing, and the u and v it leaves are a single bit each. v = 0 1, the shared bits of 00
    # and 11, gives [0]. So Peres gives [0] + [] + [0].
    assert peres([0, 0, 1, 1, 0, 1]).tolist() == [0, 0]


def test_depth_zero_is_von_neumann() -> None:
    x = coin(0.7, 10_000, seed=1)
    assert np.array_equal(peres(x, depth=0), von_neumann(x))


@pytest.mark.parametrize("bad", [[0, 2, 1], [[0, 1]], [0.5, 1]])
def test_anything_but_a_line_of_bits_is_refused(bad: list) -> None:
    with pytest.raises(ValueError, match="bits must"):
        as_bits(bad)


def test_empty_and_single_bits_give_nothing() -> None:
    assert von_neumann([]).tolist() == []
    assert peres([1]).tolist() == []


@settings(max_examples=12)
@given(bias, seed)
def test_von_neumann_output_is_fair_for_any_bias(p: float, s: int) -> None:
    out = von_neumann(coin(p, MILLION, s))
    # 4σ: a seeded draw this far out would be a real bias, not bad luck.
    assert abs(z_fair(out)) < 4


@settings(max_examples=12)
@given(bias, seed)
def test_von_neumann_yields_p_times_one_minus_p(p: float, s: int) -> None:
    # Each of the n/2 pairs survives with probability q = 2p(1−p): the count is binomial,
    # with σ = √(n/2 · q(1−q)), and the tolerance is 4σ.
    n = MILLION
    q = 2 * p * (1 - p)
    expected = n / 2 * q
    assert abs(len(von_neumann(coin(p, n, s))) - expected) < 4 * math.sqrt(n / 2 * q * (1 - q))


@settings(max_examples=12)
@given(bias, seed)
def test_peres_output_is_fair_and_its_bits_independent(p: float, s: int) -> None:
    out = peres(coin(p, MILLION, s)).astype(np.float64)
    # Even at 95% tails Peres keeps ~0.27 bits per input bit; far fewer means it broke.
    assert len(out) > 100_000
    assert abs(z_fair(out)) < 4
    centred = out - out.mean()
    lag1 = float(centred[:-1] @ centred[1:]) / float(centred @ centred)
    assert abs(lag1 * math.sqrt(len(out))) < 4


@settings(max_examples=12)
@given(bias, seed)
def test_peres_yields_strictly_more_than_von_neumann(p: float, s: int) -> None:
    x = coin(p, MILLION, s)
    assert len(peres(x)) > len(von_neumann(x))


def test_peres_approaches_the_entropy() -> None:
    # At 70% tails a bit carries h = 0.881 bits of entropy; von Neumann keeps 0.21 per bit.
    p = 0.7
    h = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    x = coin(p, MILLION, seed=2)
    rate = len(peres(x)) / len(x)
    assert len(von_neumann(x)) / len(x) == pytest.approx(p * (1 - p), abs=0.002)
    assert 0.9 * h < rate <= h
