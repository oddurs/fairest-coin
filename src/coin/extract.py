"""Turning biased bits into fair ones.

Von Neumann's trick: take the bits in pairs, keep 01 as 0 and 10 as 1, and throw away 00 and
11. If every bit is tails with the same probability p, independently, then 01 and 10 are
equally likely (each p(1−p)), so what survives is exactly fair, whatever p is. Nothing has
to be known about the coin.

The price is throughput, p(1−p) output bits per input bit, at most a quarter. Peres's
iteration recovers much of what is thrown away, approaching the coin's entropy.

The guarantee rests entirely on the input bits being independent and identically
distributed. Spike 0028 found hardware qubits where they are not, and there von Neumann's
output still passes a fairness test while its bits are correlated with each other: these
functions never check their assumption, and cannot.

Toeplitz hashing needs much less. If a block of n bits has min-entropy k (no single
sequence of them is likelier than 2^−k), however the bits depend on each other, multiplying
it by a random Toeplitz matrix gives m = k − 2·log₂(1/ε) bits within ε of uniform: the
leftover hash lemma. The matrix comes from a seed that must be uniform but may be public.
What it needs instead of independence is an honest lower bound on the min-entropy.
"""

import math
import secrets
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Bits = npt.NDArray[np.uint8]

# Depth d runs d + 1 levels of extraction, 2^(d+1) − 1 calls in all: 2,047 at depth 10, which
# keeps 93–96% of the entropy for biases between 50% and 95% (measured on 10⁶ bits).
PERES_DEPTH = 10


def as_bits(bits: npt.ArrayLike) -> Bits:
    """A one-dimensional array of 0s and 1s, or ValueError."""
    array = np.asarray(bits)
    if array.ndim != 1:
        raise ValueError(f"bits must be one-dimensional, got shape {array.shape}")
    if array.size and not np.isin(array, (0, 1)).all():
        raise ValueError("bits must be 0 or 1")
    return array.astype(np.uint8, copy=False)


def _pairs(x: Bits) -> tuple[Bits, npt.NDArray[np.bool_]]:
    """The bits as consecutive pairs (an odd last bit dropped), and which pairs differ."""
    pairs = x[: len(x) // 2 * 2].reshape(-1, 2)
    return pairs, pairs[:, 0] != pairs[:, 1]


def von_neumann(bits: npt.ArrayLike) -> Bits:
    """Fair bits from independent, identically biased ones: 01 gives 0, 10 gives 1.

    Bits are paired in order, (b0, b1), (b2, b3), and so on; an odd last bit is dropped.
    """
    pairs, differ = _pairs(as_bits(bits))
    return pairs[differ, 0]


def peres(bits: npt.ArrayLike, depth: int = PERES_DEPTH) -> Bits:
    """Von Neumann's output, then Peres's from what it discarded, recursively.

    Two sequences are built from the pairs and extracted in turn: u, whether each pair's bits
    differed (x₁ ⊕ x₂), and v, the shared bit of each pair that did not. Both are independent
    and identically distributed when the input is, and independent of von Neumann's output,
    so the concatenation is still fair and independent (Peres, Ann. Stat. 20, 1992).
    `depth` bounds the recursion; depth 0 is plain von Neumann.
    """
    if depth < 0:
        raise ValueError(f"depth must be at least 0, got {depth}")
    return _peres(as_bits(bits), depth)


def _peres(x: Bits, depth: int) -> Bits:
    pairs, differ = _pairs(x)
    out = pairs[differ, 0]
    if depth == 0 or len(pairs) < 2:
        return out
    u = differ.astype(np.uint8)
    v = pairs[~differ, 0]
    return np.concatenate([out, _peres(u, depth - 1), _peres(v, depth - 1)])


# The statistical distance from uniform that Toeplitz output is allowed if the min-entropy
# estimate holds: 2^−32 costs 64 bits of output per block.
EPSILON = 2.0**-32
# The one-sided 99.5% normal quantile SP 800-90B uses for its upper confidence bounds.
_Z = 2.576
# The worst-block estimate splits the input into this many blocks, each at least
# _MIN_BLOCK bits so its bound stays tight.
_BLOCKS = 20
_MIN_BLOCK = 1_000
# Extraction spends only this fraction of the estimated min-entropy. Two adversarial reviews
# built sources a qubit could plausibly produce (telegraph switching with short dwell
# times, a bias cycling with a drifting or non-integer period, intermittent alternation)
# on which the estimate overstates the truth by up to 1.77 times. Half covers every one.
SAFETY = 0.5
# Predictors: copy (or invert) the bit d back for d up to _MAX_LAG, which sees periods and
# repeated blocks that long; and online Markov models up to order _MAX_ORDER.
_MAX_LAG = 1_024
_MAX_ORDER = 16
# And the commoner bit at each position modulo P, for a bias that cycles with period P.
_MAX_PERIOD = 256


def _upper(p: float, n: int) -> float:
    """A 99.5% upper confidence bound on a probability estimated from n observations."""
    if n < 2:
        return 1.0
    return min(1.0, p + _Z * math.sqrt(p * (1 - p) / (n - 1)))


def min_entropy(bits: npt.ArrayLike) -> float:
    """An estimate of the min-entropy per bit, in bits, never assuming independence.

    Min-entropy is about the best possible guess: a source has h bits per bit if no strategy
    predicts its next bit with probability above 2^−h. So the estimate is the lowest of
    several, each −log₂ of an upper bound on how well something could guess:

    - most common value (SP 800-90B §6.3.1): always guess the commoner bit;
    - worst block: the same, in each twentieth of the input (at least 1,000 bits), taking
      the most predictable, for a source whose bias switches, as qubit 34's did in spike
      0028, and looks fair on average;
    - Markov cycle (after §6.3.3): the likeliest long sequence under first-order transitions,
      −log₂ max(P₀₀, P₁₁, √(P₀₁·P₁₀));
    - predictors (after §6.3.7–6.3.10): guess each bit from earlier bits only, by copying or
      inverting the bit d back (d ≤ 1,024) or by the majority that followed the same last k
      bits so far (k ≤ 16). A guess made before seeing the bit cannot be flattered by
      hindsight, so a high hit rate is real predictability.
    - phase: the commoner bit at each position modulo P (P ≤ 256), for independent bits
      whose bias cycles, which no guess from earlier bits sees. Fitted to the whole input,
      so slightly flattered, which errs toward a lower estimate; by Jensen's inequality
      −log₂ of the average hit rate never exceeds the average min-entropy.

    Each probability carries a 99.5% upper confidence bound. Two departures from 800-90B,
    both toward caution: the Markov estimate is the long-run rate, not a 128-bit score whose
    first bit a long block cannot spend, and it is bounded, not a point estimate.

    What this cannot be is a guarantee. No estimate from data can tell a deterministic
    process from a random one if the process is clever enough: π's binary digits score
    nearly a bit per bit here, with no entropy at all. The estimate holds for sources whose
    structure is within reach of these guessers. Hardware noise (bias, drift, switching,
    memory, periodic disturbance) is; a pseudo-random generator is not. On a steady fair
    source of 10⁵ bits it gives about 0.91.
    """
    x = as_bits(bits)
    n = len(x)
    if n < 2:
        raise ValueError(f"min_entropy needs at least 2 bits, got {n}")
    ones = int(x.sum())
    guesses = [_upper(max(ones, n - ones) / n, n)]

    block = max(_MIN_BLOCK, n // _BLOCKS)
    if n >= block:
        # Every full block, and one more ending at n so the tail is never skipped.
        starts = [*range(0, n - block + 1, block), n - block]
        for start in starts:
            k = int(x[start : start + block].sum())
            guesses.append(_upper(max(k, block - k) / block, block))

    pair = np.bincount(2 * x[:-1].astype(np.int64) + x[1:], minlength=4)

    def transition(a: int, b: int) -> float:
        start = int(pair[2 * a] + pair[2 * a + 1])
        return _upper(int(pair[2 * a + b]) / start, start) if start else 1.0

    guesses.append(
        max(transition(0, 0), transition(1, 1), math.sqrt(transition(0, 1) * transition(1, 0)))
    )
    for d in range(1, min(_MAX_LAG, n - 1) + 1):
        same = int(np.count_nonzero(x[d:] == x[:-d]))
        guesses.append(_upper(max(same, n - d - same) / (n - d), n - d))
    for k in range(1, min(_MAX_ORDER, n - 1) + 1):
        hits = _markov_hits(x, k)
        guesses.append(_upper(hits / (n - k), n - k))
    positions = np.arange(n)
    for period in range(2, min(_MAX_PERIOD, n // 2) + 1):
        phase = positions % period
        ones_at = np.bincount(phase, weights=x, minlength=period)
        all_at = np.bincount(phase, minlength=period)
        hits = float(np.sum(np.maximum(ones_at, all_at - ones_at)))
        guesses.append(_upper(hits / n, n))
    return max(0.0, min(1.0, -math.log2(max(guesses))))


def _markov_hits(x: Bits, k: int) -> int:
    """How many bits an online order-k majority vote guesses right, guessing before each bit.

    For each bit after the first k, look at the k bits before it, and guess whatever has
    more often followed those k bits earlier in the sequence (0 on a tie or no history).
    Done for all positions at once: sort by context, keeping time order within each, and
    count the ones that came before each position in its own context.
    """
    n = len(x)
    context = np.zeros(n - k, dtype=np.int64)
    for j in range(k):
        context = (context << 1) | x[j : n - k + j]
    target = x[k:].astype(np.int64)
    order = np.argsort(context, kind="stable")
    c, y = context[order], target[order]
    first = np.flatnonzero(np.concatenate(([True], c[1:] != c[:-1])))
    group = np.repeat(first, np.diff(np.concatenate((first, [len(c)]))))
    seen = np.arange(len(c)) - group
    ones_before = np.cumsum(y) - y - (np.cumsum(y) - y)[group]
    guess = (2 * ones_before > seen).astype(np.int64)
    return int(np.count_nonzero(guess == y))


def secure_length(n: int, entropy_per_bit: float, epsilon: float = EPSILON) -> int:
    """How many output bits n input bits support: ⌊n·h − 2·log₂(1/ε)⌋, at least 0."""
    if not 0 < epsilon < 1:
        raise ValueError(f"epsilon must be in (0, 1), got {epsilon}")
    if not 0 <= entropy_per_bit <= 1:
        raise ValueError(f"min-entropy per bit lies in [0, 1], got {entropy_per_bit}")
    return max(0, math.floor(n * entropy_per_bit + 2 * math.log2(epsilon)))


def _fast_length(size: int) -> int:
    """The smallest 2^a·3^b·5^c ≥ size, a length the FFT handles quickly."""
    best = 1 << max(0, (size - 1).bit_length())
    p5 = 1
    while p5 < best:
        p35 = p5
        while p35 < best:
            p = p35
            while p < size:
                p *= 2
            best = min(best, p)
            p35 *= 3
        p5 *= 5
    return best


def toeplitz(bits: npt.ArrayLike, seed: npt.ArrayLike, m: int) -> Bits:
    """The m × n Toeplitz matrix T[i, j] = seed[i − j + n − 1] times the bits, over GF(2).

    The seed has n + m − 1 bits, one per diagonal. Every output bit is a sum of input bits
    along one diagonal pattern, so the product is a convolution, done here by FFT: the
    integer sums are at most n, and the rounding stays below 1e-8 at n = m = 10⁷.
    """
    x = as_bits(bits)
    s = as_bits(seed)
    n = len(x)
    if n == 0:
        raise ValueError("toeplitz needs at least one input bit")
    if m < 1:
        raise ValueError(f"m must be at least 1, got {m}")
    if len(s) != n + m - 1:
        raise ValueError(f"the seed must have n + m - 1 = {n + m - 1} bits, got {len(s)}")
    size = _fast_length(len(s) + n - 1)
    spectrum = np.fft.rfft(s.astype(np.float64), size) * np.fft.rfft(x.astype(np.float64), size)
    sums = np.rint(np.fft.irfft(spectrum, size)[n - 1 : n - 1 + m]).astype(np.int64)
    return (sums % 2).astype(np.uint8)


def seed_bits(n: int) -> Bits:
    """n uniform bits from the operating system, for a Toeplitz seed."""
    return np.unpackbits(np.frombuffer(secrets.token_bytes((n + 7) // 8), dtype=np.uint8))[:n]


@dataclass(frozen=True)
class Extraction:
    """Toeplitz output, with what it rests on: record these alongside the bits."""

    bits: Bits
    entropy_per_bit: float  # the min-entropy per input bit the length was computed from
    estimate: float | None  # min_entropy's estimate, when entropy_per_bit came from it
    epsilon: float  # distance from uniform, if entropy_per_bit is a true lower bound
    input_bits: int
    seed_used: int  # how many seed bits the matrix took: input_bits + len(bits) − 1


def toeplitz_extract(
    bits: npt.ArrayLike,
    seed: npt.ArrayLike,
    *,
    entropy_per_bit: float | None = None,
    length: int | None = None,
    epsilon: float = EPSILON,
) -> Extraction:
    """Near-uniform bits from a source with enough min-entropy: no independence assumed.

    The output is within ε of uniform *if* `entropy_per_bit` is a true lower bound. By
    default it is SAFETY (one half) times `min_entropy`'s estimate of these same bits. The
    estimate can be wrong: each of its bounds fails about 0.5% of the time, it cannot see
    every dependence, and reviews found plausible sources it overstates by up to 1.77
    times, which the margin covers. So the guarantee is conditional on the source being
    within the reach of the estimate and the margin, and the chance it fails is far larger
    than ε. An `entropy_per_bit` passed in is used as given: that is the caller's claim.

    The output is as long as the leftover hash lemma allows, or `length` if shorter; asking
    for more is refused. The seed must have at least n + m − 1 bits; the first n + m − 1
    are used.
    """
    x = as_bits(bits)
    if length is not None and length < 1:
        raise ValueError(f"length must be at least 1, got {length}")
    estimate = min_entropy(x) if entropy_per_bit is None else None
    h = SAFETY * estimate if estimate is not None else entropy_per_bit
    assert h is not None
    allowed = secure_length(len(x), h, epsilon)
    m = allowed if length is None else length
    if m > allowed:
        raise ValueError(
            f"{len(x)} bits at {h:.4f} bits of min-entropy each support {allowed} output bits "
            f"at ε = {epsilon:.1e}; refusing to give {m}"
        )
    if m < 1:
        raise ValueError(f"{len(x)} bits at {h:.4f} bits each are too few to extract anything")
    s = as_bits(seed)
    if len(s) < len(x) + m - 1:
        raise ValueError(f"the seed needs at least {len(x) + m - 1} bits, got {len(s)}")
    out = toeplitz(x, s[: len(x) + m - 1], m)
    return Extraction(out, h, estimate, epsilon, len(x), len(x) + m - 1)
