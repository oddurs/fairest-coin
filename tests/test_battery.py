import math

import numpy as np
import pytest

from coin.battery import (
    ALPHA,
    _run_class_probabilities,
    battery,
    block_frequency,
    igamc,
    longest_run,
    monobit,
    passes,
    pi_bits,
    runs,
    serial,
)
from coin.extract import von_neumann

# SP 800-22 prints its p-values to six decimal places.
PUBLISHED = 5e-7
# Exact arithmetic, up to double rounding.
EXACT = 1e-12

# The 100-bit example sequence that SP 800-22 uses throughout §2: the first 100 bits of π.
NIST_100 = (
    "11001001000011111101101010100010001000010110100011"
    "00001000110100110001001100011001100010100010111000"
)
# §2.4.8's 128-bit example for the longest run of ones.
NIST_128 = (
    "1100110000010101011011000100110011100000000000100100110101010001"
    "0001001111010110100000001101011111001100111001101101100010110010"
)


def bits(text: str) -> np.ndarray:
    return np.array([int(c) for c in text], dtype=np.uint8)


@pytest.mark.parametrize(
    ("test", "sequence", "p"),
    [
        (monobit, "1011010101", 0.527089),  # §2.1.4
        (monobit, NIST_100, 0.109599),  # §2.1.8
        (lambda x: block_frequency(x, block=3), "0110011010", 0.801252),  # §2.2.4
        (lambda x: block_frequency(x, block=10), NIST_100, 0.706438),  # §2.2.8
        (runs, "1001101011", 0.147232),  # §2.3.4
        (runs, NIST_100, 0.500798),  # §2.3.8
        (longest_run, NIST_128, 0.180609),  # §2.4.8
        (lambda x: serial(x, m=3)[0], "0011011101", 0.808792),  # §2.11.4
        (lambda x: serial(x, m=3)[1], "0011011101", 0.670320),  # §2.11.4
    ],
)
def test_each_test_reproduces_the_worked_example(test, sequence: str, p: float) -> None:
    assert test(bits(sequence)) == pytest.approx(p, abs=PUBLISHED)


def test_the_example_sequence_is_pi() -> None:
    assert "".join(map(str, pi_bits(100))) == NIST_100


@pytest.mark.parametrize("a", [1, 2, 3, 7, 50])
@pytest.mark.parametrize("x", [0.1, 1.0, 4.5, 30.0, 120.0])
def test_igamc_for_whole_a_is_a_poisson_tail(a: int, x: float) -> None:
    # Q(n, x) = e^(−x) Σ_{k<n} x^k / k!: the chance of fewer than n Poisson(x) events.
    exact = math.exp(-x) * sum(x**k / math.factorial(k) for k in range(a))
    assert igamc(a, x) == pytest.approx(exact, rel=1e-10, abs=1e-300)


@pytest.mark.parametrize("x", [0.01, 0.5, 2.0, 10.0, 40.0])
def test_igamc_for_a_half_is_erfc(x: float) -> None:
    assert igamc(0.5, x) == pytest.approx(math.erfc(math.sqrt(x)), rel=1e-10, abs=1e-300)


def test_a_one_percent_bias_fails_and_von_neumann_fixes_it() -> None:
    # 51% tails over 10⁶ bits is 20σ from fair; von Neumann's output of the same bits is fair.
    x = (np.random.default_rng(1).random(1_000_000) < 0.51).astype(np.uint8)
    assert monobit(x) < 1e-50
    assert monobit(von_neumann(x)) >= ALPHA


def test_shot_to_shot_correlation_fails_serial_but_passes_monobit() -> None:
    # A fair coin that repeats its last bit 5% of the time: the frequency is perfect, the
    # pairs are not.
    rng = np.random.default_rng(2)
    x = np.empty(200_000, dtype=np.uint8)
    x[0] = 0
    fresh = rng.random(len(x)) < 0.5
    keep = rng.random(len(x)) < 0.05
    for t in range(1, len(x)):
        x[t] = x[t - 1] if keep[t] else fresh[t]
    assert monobit(x) >= ALPHA
    assert serial(x)[0] < 1e-6


def test_random_bits_pass() -> None:
    results = battery((np.random.default_rng(3).random(1_000_000) < 0.5).astype(np.uint8))
    assert passes(results), results


def test_pi_passes_the_battery() -> None:
    # The punchline. Nothing is less random than π: every bit was fixed before anyone looked.
    # The battery cannot tell. A test can show a sequence is not random; never that it is.
    results = battery(pi_bits(1_000_000))
    assert passes(results), results
    assert set(results) == {
        "monobit",
        "block frequency",
        "runs",
        "longest run",
        "serial",
        "serial (second difference)",
    }


def test_runs_is_not_applied_when_the_frequency_is_off() -> None:
    # §2.3.4: with n = 100 the prerequisite is |π − ½| < 2/√n = 0.2; 80 ones fails it, so the
    # runs test reports 0 rather than a p-value.
    assert runs(bits("1" * 80 + "0" * 20)) == pytest.approx(0.0, abs=EXACT)


def test_run_class_probabilities_match_nist() -> None:
    # Exact for M = 8, as in NIST's reference code.
    assert _run_class_probabilities(8, 1, 4) == pytest.approx(
        (55 / 256, 94 / 256, 59 / 256, 48 / 256), abs=EXACT
    )
    # For M = 128 the reference code carries nine or ten digits, which the count matches.
    assert _run_class_probabilities(128, 4, 9) == pytest.approx(
        (0.1174035788, 0.242955959, 0.249363483, 0.17517706, 0.102701071, 0.112398847),
        abs=5e-9,
    )
    # For M = 10,000, §2.4.4's table is not the exact count: it gives P(v ≤ 10) = 0.0882
    # where counting gives 0.0866 (and the asymptotic e^(−M/2^12) gives 0.0871). The module
    # uses the count, so its p-values for n ≥ 750,000 differ slightly from NIST's tool.
    exact = _run_class_probabilities(10_000, 10, 16)
    table = (0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727)
    assert sum(exact) == pytest.approx(1.0, abs=1e-12)
    assert exact[0] == pytest.approx(0.08663, abs=1e-5)
    assert exact == pytest.approx(table, abs=0.002)
    assert max(abs(a - b) for a, b in zip(exact, table, strict=True)) > 1e-3


@pytest.mark.parametrize("n", range(4, 14))
def test_serial_gives_a_p_value_for_every_short_sequence(n: int) -> None:
    # Rounding once made a zero statistic slightly negative, and igamc refused it.
    for value in range(2**n):
        x = np.array([(value >> k) & 1 for k in range(n)], dtype=np.uint8)
        p1, p2 = serial(x)
        assert 0 <= p1 <= 1
        assert 0 <= p2 <= 1


@pytest.mark.parametrize("text", ["0", "1", "1111", "0" * 10, "1" * 15])
def test_a_constant_sequence_fails_runs_at_any_length(text: str) -> None:
    assert runs(bits(text)) == pytest.approx(0.0, abs=EXACT)


def test_longest_run_counts_runs_that_span_the_whole_block() -> None:
    # A block of all ones (run 8) and one of all zeros (run 0), where a run-detection
    # off-by-one would show first, against the obvious per-block loop.
    x = np.array([1] * 8 + [0] * 8 + [1, 0] * 56, dtype=np.uint8)
    assert longest_run(x) == pytest.approx(_slow_longest_run(x), abs=EXACT)


def _slow_longest_run(x: np.ndarray) -> float:
    """The obvious per-block loop, as the reference for the vectorized version."""
    m, low, high = 8, 1, 4
    probabilities = _run_class_probabilities(m, low, high)
    blocks = len(x) // m
    counts = [0] * len(probabilities)
    for b in range(blocks):
        block = "".join(map(str, x[b * m : (b + 1) * m]))
        longest = max(len(r) for r in block.split("0"))
        counts[min(max(longest, low), high) - low] += 1
    chi2 = sum(
        (c - blocks * p) ** 2 / (blocks * p) for c, p in zip(counts, probabilities, strict=True)
    )
    return igamc((len(probabilities) - 1) / 2, chi2 / 2)


@pytest.mark.parametrize("seed", range(5))
def test_longest_run_matches_the_slow_reference(seed: int) -> None:
    x = (np.random.default_rng(seed).random(1000) < 0.6).astype(np.uint8)
    assert longest_run(x) == pytest.approx(_slow_longest_run(x), abs=EXACT)


@pytest.mark.parametrize("shift", range(10))
def test_serial_wraps_the_sequence_around(shift: int) -> None:
    # §2.11 counts patterns on the sequence joined end to start, so every rotation of the
    # worked example has the same patterns and the same p-values.
    x = np.roll(np.array([int(c) for c in "0011011101"], dtype=np.uint8), shift)
    p1, p2 = serial(x, m=3)
    assert (round(p1, 6), round(p2, 6)) == (0.808792, 0.670320)
