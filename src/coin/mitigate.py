"""Readout mitigation: correcting an *estimated distribution* for a faulty measurement.

A measurement that misreads 0 as 1 with probability p₁|₀ and 1 as 0 with p₀|₁ turns the
true distribution into a blurred one, through a known matrix. Inverting that matrix
recovers a better estimate of the true distribution from the measured frequencies.

It acts on distributions, not on bits. A single misread flip stays misread; no
arithmetic can tell which flips were wrong. Mitigation gives a better *estimate of the
bias*. It does not make one bit fairer, and nothing it returns can be spent as a random
bit. Fixing the bits themselves is extraction's job (`coin.extract`).

The confusion matrix should come from calibration circuits run under the same conditions
as the experiment: prepare |0⟩ and measure, prepare |1⟩ and measure. The chip map (0023)
found that the backend's published readout numbers did not describe the readout a job
actually got.
"""

import math

import numpy as np
import numpy.typing as npt

from coin.noise import Readout

# Inverting a readout multiplies sampling noise by 1/(1 − p₁|₀ − p₀|₁). Below this contrast
# that is more than twentyfold, and the "corrected" distribution would be mostly noise.
MIN_CONTRAST = 0.05
# The dense correction holds 2^n numbers; past this many bits, correct per-bit marginals.
MAX_WIDTH = 20
# Frequencies must sum to one up to rounding in whoever divided the counts.
_NORMALISED = 1e-9


def readout_from_counts(
    prepared_0: dict[str, int], prepared_1: dict[str, int], bit: int = 0
) -> Readout:
    """One classical bit's readout error, from shots of a prepared |0⟩ and a prepared |1⟩.

    The counts may cover many bits at once, as a whole-chip calibration job's do; `bit`
    picks which (classical bit 0 is rightmost).
    """
    zeros, ones = sum(prepared_0.values()), sum(prepared_1.values())
    if zeros == 0 or ones == 0:
        raise ValueError("both calibration circuits need at least one shot")

    def reads(counts: dict[str, int], value: str) -> int:
        total = 0
        for outcome, count in counts.items():
            if not 0 <= bit < len(outcome):
                raise ValueError(f"classical bit {bit} is not in outcome {outcome!r}")
            total += count if outcome[len(outcome) - 1 - bit] == value else 0
        return total

    return Readout(
        p1_given_0=reads(prepared_0, "1") / zeros,
        p0_given_1=reads(prepared_1, "0") / ones,
    )


def mitigate(measured: dict[str, float], errors: dict[int, Readout]) -> dict[str, float]:
    """The distribution most consistent with `measured`, given each bit's readout error.

    Inverts each bit's confusion matrix (bits are misread independently, as `apply_readout`
    models them), then projects onto the probability simplex: the nearest distribution in
    Euclidean distance with no negative entries, summing to one (Smolin, Gambetta and Smith,
    PRL 108, 070502, 2012). Raw inversion alone can give negative probabilities whenever
    sampling noise is larger than the true probability of a rare outcome.

    `measured` maps outcome strings (classical bit 0 rightmost) to frequencies summing to 1.
    Every bit of the outcomes needs an entry in `errors`; a perfect bit is Readout(0, 0).
    """
    if not measured:
        raise ValueError("nothing measured")
    widths = {len(outcome) for outcome in measured}
    if len(widths) != 1:
        raise ValueError(f"outcomes have different widths: {sorted(widths)}")
    (n,) = widths
    if any(set(outcome) - {"0", "1"} for outcome in measured):
        raise ValueError("outcomes must be strings of 0 and 1")
    if n > MAX_WIDTH:
        raise ValueError(f"{n} bits is too wide to correct densely; correct per-bit marginals")
    values = list(measured.values())
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values) or not math.isclose(
        sum(values), 1.0, abs_tol=_NORMALISED
    ):
        raise ValueError("measured must hold frequencies in [0, 1] summing to 1, not counts")
    if set(errors) != set(range(n)):
        raise ValueError(f"need a readout error for each classical bit 0..{n - 1}")

    q = np.zeros((2,) * n)
    for outcome, p in measured.items():
        # Axis k is classical bit k, so the string is read right to left.
        q[tuple(int(c) for c in reversed(outcome))] = p
    for bit, error in errors.items():
        confusion = np.array(
            [[1 - error.p1_given_0, error.p0_given_1], [error.p1_given_0, 1 - error.p0_given_1]]
        )
        contrast = 1 - error.p1_given_0 - error.p0_given_1
        if contrast < MIN_CONTRAST:
            raise ValueError(
                f"bit {bit}'s readout has contrast {contrast:.3f} (below {MIN_CONTRAST}); "
                "inverting it would mostly amplify noise"
            )
        inverse = np.linalg.inv(confusion)
        q = np.moveaxis(np.tensordot(inverse, q, axes=([1], [bit])), 0, bit)

    p = _project_to_simplex(q.ravel()).reshape(q.shape)
    return {
        "".join(str(b) for b in reversed(index)): float(v)
        for index, v in np.ndenumerate(p)
        if v > 0
    }


def _project_to_simplex(v: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """The nearest point to v with no negative entries summing to 1 (Euclidean).

    Sort descending, find how many entries stay positive after subtracting a common shift,
    and subtract it (Duchi et al., ICML 2008).
    """
    u = np.sort(v)[::-1]
    cumulative = np.cumsum(u) - 1
    k = np.arange(1, len(v) + 1)
    rho = int(np.nonzero(u - cumulative / k > 0)[0][-1])
    shift = cumulative[rho] / (rho + 1)
    return np.maximum(v - shift, 0.0)
