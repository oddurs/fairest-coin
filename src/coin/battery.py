"""Statistical tests for randomness, written from NIST SP 800-22 rev. 1a.

Each test asks one question a random sequence should answer unremarkably (are there as
many ones as zeros, are the runs the right length, are the overlapping patterns equally
common?) and returns a p-value: the probability that a truly random sequence would look at
least this unusual. NIST's convention rejects at p < 0.01.

Read what passing means carefully. A test can show a sequence is *not* random; it can never
show that it is. The binary digits of π pass every test here (`pi_bits`), and nothing is
less random than π: each digit was fixed before anyone flipped anything. That is chapter 0's
point, made executable.

Only `math` and numpy: writing the tests is the lesson.
"""

import itertools
import math
from functools import cache

import numpy as np
import numpy.typing as npt

from coin.extract import as_bits

ALPHA = 0.01  # NIST's significance level

# §2.4.4: the block length M and the classes of the longest run, chosen by the length of
# the sequence: (minimum n, M, lowest class "v ≤ low", highest class "v ≥ high").
_LONGEST_RUN = ((750_000, 10_000, 10, 16), (6_272, 128, 4, 9), (128, 8, 1, 4))


@cache
def _run_class_probabilities(m: int, low: int, high: int) -> tuple[float, ...]:
    """The exact chance that M fair bits have their longest run of ones in each class.

    SP 800-22 tabulates these to four digits. Counting instead: a(n), the number of n-bit
    strings with no run of ones longer than k, is 2^n up to n = k and then the sum of the
    k + 1 before it (a string ends in 0 after a run of 0..k ones). Exact integers throughout;
    for M = 8 this gives NIST's 55/256, 94/256, 59/256, 48/256, and for M = 128 it matches
    NIST's reference code to its nine digits. For M = 10,000 the published table is off by
    up to 0.0016 (P(v ≤ 10) is 0.0866, not 0.0882), so p-values for sequences of 750,000
    bits or more differ slightly from NIST's tool, in the direction of being right.
    """

    def at_most(k: int) -> int:
        a = [2**n for n in range(k + 1)]
        for n in range(k + 1, m + 1):
            a.append(sum(a[n - k - 1 : n]))
        return a[m]

    total = 2**m
    cumulative = [at_most(k) for k in range(low, high)]
    counts = [cumulative[0]] + [b - a for a, b in itertools.pairwise(cumulative)]
    counts.append(total - cumulative[-1])
    return tuple(c / total for c in counts)


# Series and continued fraction stop when a step changes the result by less than this:
# a few units in the last place of a double, the most precision there is.
_CONVERGED = 3 * 2.2e-16
# Lentz's method replaces a zero denominator with this, far below any value that matters.
_TINY = 1e-300
_MAX_ITERATIONS = 10_000


def igamc(a: float, x: float) -> float:
    """The regularized upper incomplete gamma function Q(a, x) = Γ(a, x) / Γ(a).

    A series below x = a + 1 and a continued fraction above it, where each converges fast
    (Numerical Recipes §6.2). Every p-value in SP 800-22 is erfc or this. Raises
    ArithmeticError rather than return a value that did not converge.
    """
    if a <= 0 or x < 0:
        raise ValueError(f"igamc needs a > 0 and x ≥ 0, got a={a}, x={x}")
    if x == 0:
        return 1.0
    log_prefix = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1:
        # P(a, x) = e^(−x)·x^a/Γ(a) · Σ x^k / (a(a+1)…(a+k)), and Q = 1 − P.
        term = total = 1 / a
        denominator = a
        for _ in range(_MAX_ITERATIONS):
            denominator += 1
            term *= x / denominator
            total += term
            if abs(term) < abs(total) * _CONVERGED:
                return max(0.0, 1 - total * math.exp(log_prefix))
        raise ArithmeticError(f"igamc series did not converge for a={a}, x={x}")
    # Modified Lentz evaluation of the continued fraction for Q(a, x).
    b = x + 1 - a
    c = 1 / _TINY
    d = 1 / b
    h = d
    for i in range(1, _MAX_ITERATIONS):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = d if abs(d) > _TINY else _TINY
        c = b + an / c
        c = c if abs(c) > _TINY else _TINY
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < _CONVERGED:
            return math.exp(log_prefix) * h
    raise ArithmeticError(f"igamc continued fraction did not converge for a={a}, x={x}")


def _nonempty(bits: npt.ArrayLike, test: str) -> npt.NDArray[np.uint8]:
    x = as_bits(bits)
    if len(x) == 0:
        raise ValueError(f"{test} needs at least one bit")
    return x


def monobit(bits: npt.ArrayLike) -> float:
    """§2.1: are ones and zeros equally common?"""
    x = _nonempty(bits, "monobit")
    s = abs(int(2 * x.sum()) - len(x)) / math.sqrt(len(x))
    return math.erfc(s / math.sqrt(2))


def block_frequency(bits: npt.ArrayLike, block: int | None = None) -> float:
    """§2.2: is each block of `block` bits about half ones?

    The default is the smallest block of at least 20 bits that makes fewer than 100 blocks,
    as §2.2.7 recommends.
    """
    x = as_bits(bits)
    m = block if block is not None else max(20, len(x) // 100 + 1)
    blocks = len(x) // m
    if blocks == 0:
        raise ValueError(f"block_frequency needs at least one block of {m} bits")
    fractions = x[: blocks * m].reshape(blocks, m).mean(axis=1)
    chi2 = 4 * m * float(np.sum((fractions - 0.5) ** 2))
    return igamc(blocks / 2, chi2 / 2)


def runs(bits: npt.ArrayLike) -> float:
    """§2.3: is the number of runs (maximal blocks of equal bits) what chance gives?"""
    x = _nonempty(bits, "runs")
    n = len(x)
    ones = float(x.mean())
    # §2.3.4 step 2: if the monobit frequency is already off, the runs test is not applied
    # and NIST reports p = 0. Below 16 bits that check cannot catch a constant sequence,
    # which is one run and as unrandom as a sequence gets, so it reports 0 too.
    if abs(ones - 0.5) >= 2 / math.sqrt(n) or ones in (0.0, 1.0):
        return 0.0
    v = 1 + int(np.count_nonzero(x[1:] != x[:-1]))
    spread = 2 * math.sqrt(2 * n) * ones * (1 - ones)
    return math.erfc(abs(v - 2 * n * ones * (1 - ones)) / spread)


def longest_run(bits: npt.ArrayLike) -> float:
    """§2.4: is the longest run of ones within each block as long as chance gives?"""
    x = as_bits(bits)
    n = len(x)
    choice = next(((m, lo, hi) for minimum, m, lo, hi in _LONGEST_RUN if n >= minimum), None)
    if choice is None:
        raise ValueError(f"longest_run needs at least 128 bits, got {n}")
    m, low, high = choice
    probabilities = _run_class_probabilities(m, low, high)
    blocks = n // m
    # Every block's longest run at once: separate the blocks with a 0, find where runs of
    # ones start and end, and credit each run to the block it starts in.
    padded = np.zeros((blocks, m + 1), dtype=np.int8)
    padded[:, 1:] = x[: blocks * m].reshape(blocks, m)
    edges = np.diff(np.concatenate((padded.ravel(), [0])))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    longest = np.zeros(blocks, dtype=np.int64)
    np.maximum.at(longest, starts // (m + 1), ends - starts)
    counts = np.bincount(np.clip(longest, low, high) - low, minlength=len(probabilities))
    expected = blocks * np.array(probabilities)
    chi2 = float(np.sum((counts - expected) ** 2 / expected))
    return igamc((len(probabilities) - 1) / 2, chi2 / 2)


def _psi2(x: npt.NDArray[np.uint8], m: int) -> float:
    """ψ²_m: how unevenly the 2^m overlapping m-bit patterns occur, wrapping at the end."""
    if m <= 0:
        return 0.0
    n = len(x)
    wrapped = np.concatenate((x, x[: m - 1]))
    patterns = np.zeros(n, dtype=np.int64)
    for k in range(m):
        patterns = (patterns << 1) | wrapped[k : k + n]
    counts = np.bincount(patterns, minlength=2**m)
    # In exact integers: in floating point, a difference of these that is truly zero can
    # come out a hair below it, which no χ² can be.
    squares = sum(int(c) * int(c) for c in counts)
    return (2**m * squares - n * n) / n


def serial(bits: npt.ArrayLike, m: int = 3) -> tuple[float, float]:
    """§2.11: are all overlapping m-bit patterns equally common? Two p-values.

    Patterns of length 2 compare each bit with the next, so this is the test that sees
    shot-to-shot correlation; the first p-value is for ∇ψ²_m, the second for ∇²ψ²_m.
    """
    x = as_bits(bits)
    if m < 2:
        raise ValueError(f"serial needs m ≥ 2, got {m}")
    if len(x) < m:
        raise ValueError(f"serial needs at least m = {m} bits, got {len(x)}")
    psi = [_psi2(x, m - k) for k in range(3)]
    # ∇ψ² is never negative; ∇²ψ² can be, and like NIST's reference code (whose igamc
    # returns 1 for x ≤ 0) that counts as no evidence against randomness.
    first = max(0.0, psi[0] - psi[1])
    second = max(0.0, psi[0] - 2 * psi[1] + psi[2])
    return igamc(2 ** (m - 2), first / 2), igamc(2 ** (m - 3), second / 2)


def battery(bits: npt.ArrayLike) -> dict[str, float]:
    """Every test, by name, with its default parameters."""
    x = as_bits(bits)
    serial_1, serial_2 = serial(x)
    return {
        "monobit": monobit(x),
        "block frequency": block_frequency(x),
        "runs": runs(x),
        "longest run": longest_run(x),
        "serial": serial_1,
        "serial (second difference)": serial_2,
    }


def passes(results: dict[str, float]) -> bool:
    """Whether every test's p-value is at least ALPHA."""
    return all(p >= ALPHA for p in results.values())


def pi_bits(n: int) -> npt.NDArray[np.uint8]:
    """The first n bits of π in binary, 11.00100100001111…, starting with the integer part.

    Chudnovsky's series by binary splitting, in Python integers: a million bits take about
    a second. The battery's control: perfectly deterministic, and it passes.
    """
    if n < 2:
        raise ValueError(f"pi_bits needs n ≥ 2, got {n}")
    c3 = 640320**3 // 24

    def split(a: int, b: int) -> tuple[int, int, int]:
        if b - a == 1:
            p = q = 1 if a == 0 else 0
            if a:
                p = (6 * a - 5) * (2 * a - 1) * (6 * a - 1)
                q = a * a * a * c3
            t = p * (13591409 + 545140134 * a)
            return p, q, -t if a % 2 else t
        mid = (a + b) // 2
        p1, q1, t1 = split(a, mid)
        p2, q2, t2 = split(mid, b)
        return p1 * p2, q1 * q2, q2 * t1 + p1 * t2

    # Each term adds about 14.18 decimal digits; 64 guard bits absorb the truncation.
    terms = int(n * math.log10(2) / 14.18) + 2
    _, q, t = split(0, terms)
    guard = 64
    shift = n - 2 + guard
    scaled = 426880 * math.isqrt(10005 << (2 * shift)) * q // t
    digits = bin(scaled >> guard)[2:][:n]
    return np.frombuffer(digits.encode(), dtype=np.uint8) - ord("0")
