import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import coin.mitigate
from coin.mitigate import _project_to_simplex, mitigate, readout_from_counts
from coin.noise import Readout, apply_readout

# Exact algebra: inversion and projection of a distribution, up to double rounding.
EXACT = 1e-12
# Undoing up to four confusion matrices with determinant ≥ 0.4 amplifies rounding up to
# 0.4⁻⁴ ≈ 40 times; this leaves a wide margin above that.
ROUND_TRIP = 1e-9

error_rate = st.floats(min_value=0.0, max_value=0.3)
readout = st.builds(Readout, error_rate, error_rate)


def outcomes(n: int) -> list[str]:
    return [format(i, f"0{n}b") for i in range(2**n)]


@st.composite
def distributions(draw: st.DrawFn, n: int) -> dict[str, float]:
    # Some outcomes impossible: where raw inversion goes most negative.
    weight = st.one_of(st.just(0.0), st.floats(0.01, 1.0))
    weights = draw(st.lists(weight, min_size=2**n, max_size=2**n).filter(any))
    total = sum(weights)
    return {o: w / total for o, w in zip(outcomes(n), weights, strict=True)}


@given(
    st.integers(1, 4).flatmap(
        lambda n: st.tuples(distributions(n), st.lists(readout, min_size=n, max_size=n))
    )
)
def test_mitigation_undoes_a_known_readout_error_exactly(case) -> None:
    true, errors = case
    measured = apply_readout(true, dict(enumerate(errors)))
    recovered = mitigate(measured, dict(enumerate(errors)))
    for outcome in outcomes(len(errors)):
        assert recovered.get(outcome, 0.0) == pytest.approx(true[outcome], abs=ROUND_TRIP)


@pytest.mark.parametrize("seed", range(5))
def test_mitigation_recovers_a_sampled_distribution_within_sampling_error(seed: int) -> None:
    # A biased coin read through an asymmetric readout, 100,000 shots: the mitigated P(tails)
    # lands within 4σ of the truth, where the raw frequency is far off.
    rng = np.random.default_rng(seed)
    shots = 100_000
    error = Readout(p1_given_0=0.02, p0_given_1=0.08)
    true = {"0": 0.45, "1": 0.55}
    blurred = apply_readout(true, {0: error})
    tails = rng.binomial(shots, blurred["1"])
    measured = {"0": 1 - tails / shots, "1": tails / shots}
    recovered = mitigate(measured, {0: error})
    # The inverse scales the sampling error by 1/(1 − p₁|₀ − p₀|₁).
    sigma = math.sqrt(blurred["1"] * blurred["0"] / shots) / (1 - 0.02 - 0.08)
    assert abs(recovered["1"] - 0.55) < 4 * sigma
    assert abs(measured["1"] - 0.55) > 10 * sigma


@settings(max_examples=200)
@given(
    st.integers(1, 4).flatmap(
        lambda n: st.tuples(distributions(n), st.lists(readout, min_size=n, max_size=n))
    ),
    st.integers(0, 2**32 - 1),
)
def test_mitigation_never_returns_a_negative_probability(case, seed: int) -> None:
    # Few shots and a sparse truth push raw inversion negative; the projection must not.
    true, errors = case
    n = len(errors)
    blurred = apply_readout(true, dict(enumerate(errors)))
    keys = outcomes(n)
    counts = np.random.default_rng(seed).multinomial(20, [blurred.get(k, 0.0) for k in keys])
    measured = {k: int(c) / 20 for k, c in zip(keys, counts, strict=True) if c}
    recovered = mitigate(measured, dict(enumerate(errors)))
    assert all(p >= 0 for p in recovered.values())
    assert sum(recovered.values()) == pytest.approx(1.0, abs=EXACT)


def test_raw_inversion_alone_would_go_negative() -> None:
    # Measured all heads through a readout that misreads heads 10% of the time: the raw
    # inverse says P(tails) < 0. Mitigation clips it to a distribution.
    error = Readout(p1_given_0=0.1, p0_given_1=0.1)
    inverse = np.linalg.inv(np.array([[0.9, 0.1], [0.1, 0.9]]))
    assert (inverse @ np.array([1.0, 0.0]))[1] < 0
    assert mitigate({"0": 1.0}, {0: error}) == {"0": pytest.approx(1.0, abs=EXACT)}


@given(st.lists(st.floats(-2, 2), min_size=1, max_size=16))
def test_projection_lands_on_the_simplex_and_keeps_points_already_there(v: list[float]) -> None:
    p = _project_to_simplex(np.array(v))
    assert np.all(p >= 0)
    assert p.sum() == pytest.approx(1.0, abs=EXACT)
    assert np.allclose(_project_to_simplex(p), p, atol=EXACT)


def test_readout_from_calibration_counts() -> None:
    error = readout_from_counts({"0": 980, "1": 20}, {"0": 75, "1": 925})
    assert error.p1_given_0 == pytest.approx(0.02, abs=EXACT)
    assert error.p0_given_1 == pytest.approx(0.075, abs=EXACT)


def test_the_docstring_says_mitigation_acts_on_distributions_not_bits() -> None:
    doc = coin.mitigate.__doc__ or ""
    assert "acts on distributions, not on bits" in doc
    assert "does not make one bit fairer" in doc


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: mitigate({}, {}), "nothing measured"),
        (lambda: mitigate({"0": 0.5, "11": 0.5}, {0: Readout(0, 0)}), "different widths"),
        (lambda: mitigate({"01": 1.0}, {0: Readout(0, 0)}), "each classical bit"),
        (lambda: mitigate({"0": 0.5, "1": 0.5}, {0: Readout(0.5, 0.4999999)}), "contrast"),
        (lambda: mitigate({"0": 600, "1": 400}, {0: Readout(0, 0)}), "not counts"),
        (lambda: mitigate({"0": math.nan, "1": 0.5}, {0: Readout(0, 0)}), "frequencies"),
        (lambda: mitigate({"0": 1.2, "1": -0.2}, {0: Readout(0, 0)}), "frequencies"),
        (lambda: mitigate({"2": 1.0}, {0: Readout(0, 0)}), "0 and 1"),
        # Every value at most 1 and summing to 1, but one negative: not a distribution.
        (
            lambda: mitigate(
                {"00": 0.6, "01": 0.6, "10": -0.2, "11": 0.0}, {0: Readout(0, 0), 1: Readout(0, 0)}
            ),
            "frequencies",
        ),
        (lambda: mitigate({"0": 0.5, "1": 0.5}, {0: Readout(0, 0), 1: Readout(0, 0)}), "each"),
        (lambda: mitigate({"0 1": 1.0}, {0: Readout(0, 0)}), "0 and 1"),
        (lambda: mitigate({"0" * 21: 1.0}, {}), "too wide"),
        (lambda: readout_from_counts({}, {"1": 1}), "at least one shot"),
        (lambda: readout_from_counts({"01": 1}, {"11": 1}, bit=2), "not in outcome"),
    ],
)
def test_impossible_requests_are_refused(call, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()


def test_readout_from_a_multi_bit_calibration_job() -> None:
    # Two bits calibrated at once: bit 0 misreads 0 as 1 in 100 of 1000 shots and 1 as 0 in
    # 200; bit 1 misreads 0 as 1 in 50 and 1 as 0 in 0.
    prepared_0 = {"00": 850, "01": 100, "10": 50}
    prepared_1 = {"11": 800, "10": 200}
    zero = readout_from_counts(prepared_0, prepared_1, bit=0)
    one = readout_from_counts(prepared_0, prepared_1, bit=1)
    assert (zero.p1_given_0, zero.p0_given_1) == pytest.approx((0.1, 0.2), abs=EXACT)
    assert (one.p1_given_0, one.p0_given_1) == pytest.approx((0.05, 0.0), abs=EXACT)


def test_a_readout_worse_than_random_is_refused() -> None:
    # p(1|0) + p(0|1) > 1: the contrast is negative. Inverting would flip the answer, and
    # its size alone (0.2) must not let it through.
    with pytest.raises(ValueError, match="contrast"):
        mitigate({"0": 0.5, "1": 0.5}, {0: Readout(0.6, 0.6)})
