import math
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from coin.archive import load_run
from coin.battery import ALPHA, battery, passes, pi_bits, serial
from coin.extract import (
    SAFETY,
    as_bits,
    min_entropy,
    peres,
    secure_length,
    seed_bits,
    toeplitz,
    toeplitz_extract,
    von_neumann,
)

MILLION = 1_000_000
# Exact arithmetic, up to double rounding.
EXACT = 1e-12

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


small = st.integers(min_value=1, max_value=40)


@given(st.data(), small, small)
def test_toeplitz_is_the_matrix_product_over_gf2(data: st.DataObject, n: int, m: int) -> None:
    x = np.array(data.draw(st.lists(st.integers(0, 1), min_size=n, max_size=n)), dtype=np.uint8)
    s = np.array(
        data.draw(st.lists(st.integers(0, 1), min_size=n + m - 1, max_size=n + m - 1)),
        dtype=np.uint8,
    )
    # T[i, j] = s[i − j + n − 1]: constant along each diagonal.
    t = s[np.arange(m)[:, None] - np.arange(n)[None, :] + n - 1]
    assert toeplitz(x, s, m).tolist() == ((t.astype(int) @ x) % 2).tolist()


def test_toeplitz_stays_exact_at_scale() -> None:
    # The FFT's rounding grows with size; check a product big enough to matter.
    rng = np.random.default_rng(3)
    n, m = 4000, 3000
    x, s = rng.integers(0, 2, n, dtype=np.uint8), rng.integers(0, 2, n + m - 1, dtype=np.uint8)
    t = s[np.arange(m)[:, None] - np.arange(n)[None, :] + n - 1]
    assert np.array_equal(toeplitz(x, s, m), (t.astype(np.int64) @ x) % 2)


def test_toeplitz_is_exact_where_the_sums_are_largest() -> None:
    # All ones: every output bit sums all n input bits, the largest integers the FFT must
    # round correctly. n is odd, so every output bit is 1.
    n = m = 1_000_001
    out = toeplitz(np.ones(n, dtype=np.uint8), np.ones(n + m - 1, dtype=np.uint8), m)
    assert out.min() == 1


def markov_source(stay: float, n: int, seed: int) -> np.ndarray:
    """Repeats its last bit with probability `stay`: min-entropy rate −log₂(max(stay, 1−stay))."""
    rng = np.random.default_rng(seed)
    flip = (rng.random(n) >= stay).astype(np.uint8)
    flip[0] = rng.integers(0, 2)
    return np.bitwise_xor.accumulate(flip)


@settings(max_examples=20)
@given(st.floats(min_value=0.5, max_value=0.99), seed)
def test_min_entropy_never_exceeds_an_iid_source(p: float, s: int) -> None:
    assert min_entropy(coin(p, 100_000, s)) <= -math.log2(max(p, 1 - p))


@settings(max_examples=20)
@given(st.floats(min_value=0.01, max_value=0.99), seed)
def test_min_entropy_never_exceeds_a_markov_source(stay: float, s: int) -> None:
    # A sticky chain (stay > ½) is fair bit by bit, yet carries far less than a bit each.
    assert min_entropy(markov_source(stay, 100_000, s)) <= -math.log2(max(stay, 1 - stay))


def test_min_entropy_sees_dependence_that_frequency_misses() -> None:
    x = markov_source(0.9, 100_000, seed=4)
    # The sticky chain's runs average 10 bits, so its fraction of ones has σ ≈ √(10/4n) =
    # 0.005; 0.025 is 5σ.
    assert abs(x.mean() - 0.5) < 0.025
    # True rate −log₂ 0.9 = 0.152.
    assert min_entropy(x) <= -math.log2(0.9)


def test_the_output_is_as_long_as_the_leftover_hash_lemma_allows() -> None:
    # 100,000 bits at a stated 0.5 bits each, ε = 2^−32: ⌊50,000 − 64⌋ = 49,936 bits.
    x = coin(0.5, 100_000, seed=5)
    seed_ = seed_bits(200_000)
    result = toeplitz_extract(x, seed_, entropy_per_bit=0.5)
    assert len(result.bits) == 49_936
    assert result.entropy_per_bit == pytest.approx(0.5, abs=EXACT)
    assert result.epsilon == pytest.approx(2.0**-32, rel=EXACT)
    assert (result.input_bits, result.seed_used) == (100_000, 100_000 + 49_936 - 1)
    assert len(toeplitz_extract(x, seed_, entropy_per_bit=0.5, length=1000).bits) == 1000
    with pytest.raises(ValueError, match="refusing"):
        toeplitz_extract(x, seed_, entropy_per_bit=0.5, length=49_937)


def test_the_default_length_spends_half_the_estimate() -> None:
    x = coin(0.7, 100_000, seed=5)
    result = toeplitz_extract(x, seed_bits(200_000))
    assert result.estimate == pytest.approx(min_entropy(x), abs=EXACT)
    assert result.entropy_per_bit == pytest.approx(SAFETY * min_entropy(x), abs=EXACT)
    assert len(result.bits) == secure_length(len(x), SAFETY * min_entropy(x))


def test_a_stated_entropy_is_used_as_given() -> None:
    result = toeplitz_extract(coin(0.5, 10_000, seed=1), seed_bits(20_000), entropy_per_bit=0.4)
    assert result.estimate is None
    assert result.entropy_per_bit == pytest.approx(0.4, abs=EXACT)


def test_a_length_below_one_is_a_bad_argument_not_too_little_entropy() -> None:
    with pytest.raises(ValueError, match="length must be at least 1"):
        toeplitz_extract(coin(0.5, 10_000, seed=1), seed_bits(20_000), length=0)


def test_no_estimate_can_see_that_pi_is_deterministic() -> None:
    # The limit, stated as a test: π's digits have no entropy at all, and every guesser
    # here scores them near a bit per bit. The estimate holds for physical noise, not for
    # an adversary.
    assert min_entropy(pi_bits(100_000)) > 0.85


def test_too_little_entropy_extracts_nothing() -> None:
    with pytest.raises(ValueError, match="too few"):
        toeplitz_extract(np.zeros(1000, dtype=np.uint8), seed_bits(2000))


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: secure_length(100, 0.5, epsilon=0), "epsilon"),
        (lambda: secure_length(100, 1.5), "min-entropy"),
        (lambda: toeplitz([], [], 1), "at least one input bit"),
        (lambda: toeplitz([1, 0], [1, 0], 2), "n \\+ m - 1"),
        (lambda: toeplitz([1, 0], [1], 0), "at least 1"),
        (lambda: min_entropy([1]), "at least 2"),
    ],
)
def test_impossible_requests_are_refused(call, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()


def test_secure_length_survives_the_smallest_epsilon() -> None:
    # 1/ε overflows to inf at the smallest double, 2^−1074; log₂ ε does not.
    assert secure_length(10**6, 1.0, 5e-324) == 10**6 - 2 * 1074
    assert secure_length(10**6, 1.0, 2.0**-100) == 10**6 - 200


def test_seed_bits_are_bits_of_the_requested_length() -> None:
    s = seed_bits(1001)
    assert len(s) == 1001
    assert set(np.unique(s)) <= {0, 1}


CHIP_MAP = Path(__file__).resolve().parent.parent / "data/runs/2026-11-02-dbjuh5d6p51s73cljo60"


def test_toeplitz_fixes_what_von_neumann_cannot_on_qubit_88() -> None:
    # Spike 0028: qubit 88's shots carry a periodic disturbance. Von Neumann's output of them
    # is fair but serially correlated; Toeplitz hashing of the same shots passes.
    run = load_run(CHIP_MAP)
    assert run.memory is not None
    width = len(run.memory[0])
    column = width - 1 - run.qubits.index(88)  # classical bit 0 is the rightmost character
    shots = np.frombuffer("".join(run.memory).encode(), dtype=np.uint8).reshape(-1, width)
    q88 = (shots[:, column] == ord("1")).astype(np.uint8)
    assert serial(von_neumann(q88))[0] < ALPHA
    result = toeplitz_extract(q88, np.random.default_rng(6).integers(0, 2, 200_000, dtype=np.uint8))
    # Its estimate is about 0.89 bits per shot and half of that is spent: about 44,000 bits,
    # against von Neumann's 25,503 correlated ones.
    assert len(result.bits) > 0.4 * len(q88)
    assert passes(battery(result.bits))


def telegraph_source(low: float, high: float, segment: int, n: int, seed: int) -> np.ndarray:
    """Switches between two biases every `segment` bits, like qubit 34 in spike 0028."""
    rng = np.random.default_rng(seed)
    p = np.where((np.arange(n) // segment) % 2 == 0, low, high)
    return (rng.random(n) < p).astype(np.uint8)


@pytest.mark.parametrize("seed", range(5))
def test_min_entropy_never_exceeds_a_telegraph_source(seed: int) -> None:
    # Alternating 20% and 80% tails looks fair overall, but its likeliest sequence is the one
    # that follows each stretch's commoner side: −log₂ 0.8 = 0.32 bits per bit.
    x = telegraph_source(0.2, 0.8, 10_000, 100_000, seed)
    # Equal time at 20% and 80%: ones average ½, with σ = √(0.16/n) ≈ 0.0013; 0.01 is 8σ.
    assert abs(x.mean() - 0.5) < 0.01
    assert min_entropy(x) <= -math.log2(0.8)


def order_two_source(stay: float, n: int, seed: int) -> np.ndarray:
    """Copies the bit two back with probability `stay`: −log₂(stay) per bit, invisible at lag 1."""
    rng = np.random.default_rng(seed)
    x = rng.integers(0, 2, n).astype(np.uint8)
    copy = rng.random(n) < stay
    for t in range(2, n):
        if copy[t]:
            x[t] = x[t - 2]
    return x


@pytest.mark.parametrize(
    ("name", "source", "true"),
    [
        ("pattern 0011 repeated", lambda: np.tile([0, 0, 1, 1], 25_000).astype(np.uint8), 0.0),
        ("period 5", lambda: np.tile([0, 1, 1, 0, 1], 20_000).astype(np.uint8), 0.0),
        ("1,000 random bits, repeated", lambda: np.tile(coin(0.5, 1000, 7), 100), 0.01),
        ("order-2 copying, 90%", lambda: order_two_source(0.9, 100_000, 8), -math.log2(0.9)),
        ("order-2 copying, 99%", lambda: order_two_source(0.99, 100_000, 9), -math.log2(0.99)),
    ],
)
def test_min_entropy_sees_structure_beyond_the_last_bit(name: str, source, true: float) -> None:
    # Each of these fooled the bias, lag-1 Markov and worst-block estimates into ~0.5-0.95.
    assert min_entropy(source()) <= true + 0.01, name


def cycling_bias(p: np.ndarray, n: int, seed: int) -> tuple[np.ndarray, float]:
    """Independent bits whose bias follows the cycle p; returns them and the true rate."""
    bias = np.resize(p, n)
    bits = (np.random.default_rng(seed).random(n) < bias).astype(np.uint8)
    return bits, float(np.mean(-np.log2(np.maximum(bias, 1 - bias))))


@pytest.mark.parametrize(
    "cycle",
    [
        np.array([0.6, 0.4]),
        0.5 + 0.3 * np.cos(2 * np.pi * np.arange(3) / 3),
        0.5 + 0.3 * np.cos(2 * np.pi * np.arange(8) / 8),
        0.5 + 0.3 * np.sin(2 * np.pi * np.arange(200) / 200),
    ],
    ids=["period 2", "period 3", "period 8", "period 200"],
)
def test_min_entropy_sees_a_bias_that_cycles(cycle: np.ndarray) -> None:
    # Each bit independent, but its bias depends on its position in the cycle: a guesser that
    # knows the phase does better than any guess from earlier bits.
    x, true = cycling_bias(cycle, 100_000, seed=10)
    assert min_entropy(x) <= true


def drifting_cycle(periods: np.ndarray, n: int, seed: int) -> tuple[np.ndarray, float]:
    """Independent bits, bias 0.5 + 0.3·sin of a phase advancing 1/period per bit."""
    phase = np.cumsum(1 / np.resize(periods, n))
    bias = 0.5 + 0.3 * np.sin(2 * np.pi * phase)
    bits = (np.random.default_rng(11).random(n) < bias).astype(np.uint8)
    return bits, float(np.mean(-np.log2(np.maximum(bias, 1 - bias))))


@pytest.mark.parametrize(
    "periods",
    [np.array([50.7]), np.array([300.5]), np.linspace(40, 60, 100_000)],
    ids=["period 50.7", "period 300.5", "chirp 40 to 60"],
)
def test_the_safety_margin_covers_what_the_estimate_misses(periods: np.ndarray) -> None:
    # The second review's sources: the bias cycles, but not with a whole period the phase
    # guesser can fit, and the estimate lands above the truth. Half of it does not.
    x, true = drifting_cycle(periods, 100_000, seed=11)
    assert min_entropy(x) > true  # the miss, kept visible
    assert SAFETY * min_entropy(x) <= true


@pytest.mark.parametrize(("dwell", "bound"), [(5, 0.615), (20, 0.395)])
def test_the_safety_margin_stays_under_a_short_dwell_telegraph(dwell: int, bound: float) -> None:
    # Switches between 20% and 80% tails, staying put each bit with probability 1 − 1/dwell.
    # The bound is the review's forward-algorithm upper bound on the true rate, so this
    # checks a necessary condition, not the whole guarantee.
    rng = np.random.default_rng(12)
    switch = rng.random(100_000) < 1 / dwell
    state = np.bitwise_xor.accumulate(switch.astype(np.uint8))
    x = (rng.random(100_000) < np.where(state == 1, 0.8, 0.2)).astype(np.uint8)
    assert SAFETY * min_entropy(x) <= bound
