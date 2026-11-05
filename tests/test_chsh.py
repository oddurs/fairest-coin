import math
from typing import Any

import numpy as np
import pytest

from coin import chsh
from coin.compile import lower
from coin.noise import Readout
from coin.sim import probabilities
from tests.test_harvest import cli_run

EXACT = 1e-12


def test_the_ideal_bell_pair_reaches_tsirelsons_bound() -> None:
    correlations = {
        (i, j): chsh.correlation(probabilities(lower(chsh.circuit(a, b))))
        for i, a in enumerate(chsh.ALICE)
        for j, b in enumerate(chsh.BOB)
    }
    for (i, j), e in correlations.items():
        assert e == pytest.approx(math.cos(chsh.ALICE[i] - chsh.BOB[j]), abs=EXACT)
    assert chsh.s_value(correlations) == pytest.approx(2 * math.sqrt(2), abs=EXACT)


def test_correlation_counts_agreement_minus_disagreement() -> None:
    assert chsh.correlation({"00": 0.4, "11": 0.3, "01": 0.2, "10": 0.1}) == pytest.approx(0.4)


def qubit(p1_given_0: float, p0_given_1: float) -> list[dict[str, Any]]:
    # T1 = T2 = ∞: no relaxation, so the depolarizing and readout errors are the whole model.
    return [
        {"name": "T1", "value": math.inf, "unit": "us"},
        {"name": "T2", "value": math.inf, "unit": "us"},
        {"name": "prob_meas1_prep0", "value": p1_given_0, "unit": ""},
        {"name": "prob_meas0_prep1", "value": p0_given_1, "unit": ""},
    ]


def gate(name: str, qubits: list[int], error: float, length: float = 60) -> dict[str, Any]:
    return {
        "gate": name,
        "qubits": qubits,
        "parameters": [
            {"name": "gate_error", "value": error, "unit": ""},
            {"name": "gate_length", "value": length, "unit": "ns"},
        ],
    }


# A line 0–1–2–3, plus qubit 4 coupled to nothing. Pair (0, 1) has the best cz but qubit 0
# reads badly; (2, 3) has a worse cz and good readout; qubit 3's readout is asymmetric.
READOUT = {0: (0.05, 0.05), 1: (0.01, 0.01), 2: (0.01, 0.01), 3: (0.005, 0.02), 4: (0.0, 0.0)}
CZ = {(0, 1): 0.002, (1, 2): 0.010, (2, 3): 0.004}
CALIBRATION: dict[str, Any] = {
    "qubits": [qubit(*READOUT[q]) for q in range(5)],
    "gates": [gate("sx", [q], 0.0, 36) for q in range(5)]
    + [gate("cz", list(pair), error) for pair, error in CZ.items()]
    + [gate("cz", list(reversed(pair)), error) for pair, error in CZ.items()],
}


def analytic_s(pair: tuple[int, int], readout: dict[int, tuple[float, float]]) -> float:
    """S with depolarizing noise and readout only, by hand.

    Depolarizing p on the pair scales every correlation by 1 − p, and p = 4r/3 for a gate of
    average error r in four dimensions. Each readout maps a ±1 outcome z to c·z + d on
    average, with c = 1 − p(1|0) − p(0|1) and d = p(0|1) − p(1|0); Alice's and Bob's
    marginals are 0 in every setting, so E becomes c_A·c_B·E + d_A·d_B and S gains 2·d_A·d_B.
    """
    c = {q: 1 - sum(readout[q]) for q in pair}
    d = {q: readout[q][1] - readout[q][0] for q in pair}
    a, b = pair
    return c[a] * c[b] * chsh.TSIRELSON * (1 - 4 * CZ[pair] / 3) + 2 * d[a] * d[b]


def test_every_pair_scores_what_the_analytic_model_gives() -> None:
    ranked = chsh.rank_pairs(CALIBRATION)
    for score in ranked:
        assert score.s == pytest.approx(analytic_s(score.pair, READOUT), abs=1e-9)
    best = max(CZ, key=lambda pair: analytic_s(pair, READOUT))
    assert ranked[0].pair == best == (2, 3)
    # Neither the best cz nor the best readout alone would have chosen it.
    assert min(CZ, key=CZ.__getitem__) == (0, 1)


def test_only_coupled_pairs_are_scored() -> None:
    # Qubit 4 reads perfectly, but it is coupled to nothing, so it never appears.
    assert {score.pair for score in chsh.rank_pairs(CALIBRATION)} == set(CZ)


def test_measured_readout_replaces_the_published_and_says_so() -> None:
    # Measured in the same session, qubit 3 turns out to read badly: (1, 2) now wins.
    measured = {3: Readout(0.06, 0.06)}
    ranked = chsh.rank_pairs(CALIBRATION, measured)
    assert ranked[0].pair == (1, 2)
    sources = {score.pair: score.readout_source for score in ranked}
    assert sources[2, 3] == ("published", "measured")
    assert sources[1, 2] == ("published", "published")
    readout = {**READOUT, 3: (0.06, 0.06)}
    scores = {score.pair: score.s for score in ranked}
    assert scores[2, 3] == pytest.approx(analytic_s((2, 3), readout), abs=1e-9)


def test_a_pair_whose_cz_is_marked_failed_is_left_out() -> None:
    broken = {
        **CALIBRATION,
        "gates": [g for g in CALIBRATION["gates"] if g["qubits"] != [3, 2]]
        + [gate("cz", [3, 2], 1.0)],
    }
    assert (2, 3) not in {score.pair for score in chsh.rank_pairs(broken)}


def test_relaxation_during_the_cz_lowers_s() -> None:
    # Qubits 2 and 3 now decay (T1 = 100 µs, T2 = 80 µs); the others still do not.
    decay = [
        {"name": "T1", "value": 100, "unit": "us"},
        {"name": "T2", "value": 80, "unit": "us"},
    ]
    qubits = [decay + q[2:] if i in (2, 3) else q for i, q in enumerate(CALIBRATION["qubits"])]
    fast = {score.pair: score.s for score in chsh.rank_pairs(CALIBRATION)}
    slow = {score.pair: score.s for score in chsh.rank_pairs({**CALIBRATION, "qubits": qubits})}
    assert slow[2, 3] < fast[2, 3]
    assert slow[0, 1] == pytest.approx(fast[0, 1], abs=EXACT)


def test_coin_predict_lists_the_best_pairs(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    import json  # noqa: PLC0415

    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(CALIBRATION, allow_nan=True))
    code, out, _ = cli_run(["predict", "--calibration", str(path), "--pairs"], capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "3 coupled pairs scored; the best 3:"
    assert lines[2].split() == [
        "2-3",
        f"{analytic_s((2, 3), READOUT):.4f}",
        "0.00400",
        "published,",
        "published",
    ]


def test_readout_runs_only_go_with_pairs(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli_run(["predict", "--calibration", "x", "--readout", "a", "b"], capsys)
    assert code == 2
    assert "--readout is for --pairs" in err


def test_the_two_qubit_depolarizing_channel_scrambles_completely_at_p_1() -> None:
    from coin.noise import pair_depolarizing  # noqa: PLC0415
    from coin.sim import _conjugate  # noqa: PLC0415

    rho = np.zeros((2, 2, 2, 2), dtype=np.complex128)
    rho[0, 0, 0, 0] = 1
    channel = pair_depolarizing(1.0, (0, 1))
    out = sum(_conjugate(rho, k, channel.qubits, 2) for k in channel.kraus)
    assert np.allclose(np.asarray(out).reshape(4, 4), np.eye(4) / 4, atol=EXACT)


# ─── S from counts ───────────────────────────────────────────────────────────────────────

SETTINGS = [(i, j) for i in (0, 1) for j in (0, 1)]


def quantum_counts(
    shots: int, rng: np.random.Generator, visibility: float = 1.0
) -> dict[tuple[int, int], dict[str, int]]:
    """Each setting's counts from the simulated Bell pair, depolarized to `visibility`."""
    from coin.noise import pair_depolarizing  # noqa: PLC0415
    from coin.sim import sample  # noqa: PLC0415

    def noise(op: object) -> tuple[Any, ...]:
        # Right after the cz the pair is (|00⟩ + |11⟩)/√2; scrambling it with probability
        # 1 − V leaves V·ρ + (1 − V)·I/4, whose every correlation is V times the ideal.
        if getattr(op, "name", None) == "cz":
            return (pair_depolarizing(1 - visibility, (0, 1)),)
        return ()

    return {
        (i, j): sample(lower(chsh.circuit(chsh.ALICE[i], chsh.BOB[j])), shots, rng, noise)
        for i, j in SETTINGS
    }


def test_an_ideal_bell_pair_gives_tsirelsons_bound_within_sampling_error() -> None:
    result = chsh.estimate(quantum_counts(20_000, np.random.default_rng(1)))
    assert abs(result.s - chsh.TSIRELSON) < 4 * result.standard_error
    assert result.rounds == 80_000


@pytest.mark.parametrize("visibility", [0.95, 0.8, 0.6, 0.3])
def test_a_depolarized_pair_gives_s_times_its_visibility(visibility: float) -> None:
    result = chsh.estimate(quantum_counts(20_000, np.random.default_rng(2), visibility))
    assert abs(result.s - chsh.TSIRELSON * visibility) < 4 * result.standard_error


def test_the_standard_error_is_the_binomial_one() -> None:
    # E = 0.5 from 100 shots per setting: each variance (1 − 0.25)/100, four of them.
    counts = {setting: {"00": 75, "01": 25} for setting in SETTINGS}
    result = chsh.estimate(counts)
    assert result.s == pytest.approx(0.5 + 0.5 + 0.5 - 0.5)
    assert result.standard_error == pytest.approx(math.sqrt(4 * 0.75 / 100))


def local_counts(
    rounds: int, rng: np.random.Generator, strategies: list[tuple[tuple[int, int], tuple[int, int]]]
) -> dict[tuple[int, int], dict[str, int]]:
    """A local hidden-variable model: each round a hidden strategy is drawn, shared by both
    sides in advance, and each answers from it and its own setting alone. Settings are drawn
    uniformly each round, as the game requires."""
    counts: dict[tuple[int, int], dict[str, int]] = {s: {} for s in SETTINGS}
    chosen = rng.integers(0, len(strategies), rounds)
    settings = rng.integers(0, 2, (rounds, 2))
    for k, (i, j) in zip(chosen.tolist(), settings.tolist(), strict=True):
        alice, bob = strategies[k]
        outcome = f"{bob[j]}{alice[i]}"
        counts[i, j][outcome] = counts[i, j].get(outcome, 0) + 1
    return counts


DETERMINISTIC = [
    ((a0, a1), (b0, b1)) for a0 in (0, 1) for a1 in (0, 1) for b0 in (0, 1) for b1 in (0, 1)
]


@pytest.mark.parametrize("seed", range(5))
def test_a_local_model_never_exceeds_2_beyond_sampling_error(seed: int) -> None:
    rng = np.random.default_rng(seed)
    # A random mixture of all sixteen deterministic strategies, and the best one alone.
    mixture = [DETERMINISTIC[k] for k in rng.integers(0, 16, 6)]
    for strategies in (mixture, [((0, 0), (0, 0))]):
        result = chsh.estimate(local_counts(20_000, rng, strategies))
        assert result.s <= 2 + 4 * result.standard_error


def test_s_low_rarely_exceeds_2_for_a_local_model() -> None:
    # The best local strategy wins exactly 3/4 of rounds (S = 2). At ε = 0.1, S_low may
    # exceed 2 in at most a tenth of runs; Hoeffding is conservative, so it should be fewer.
    rng = np.random.default_rng(7)
    epsilon, runs = 0.1, 400
    above = sum(
        chsh.estimate(local_counts(2_000, rng, [((0, 0), (0, 0))])).lower_bound(epsilon) > 2
        for _ in range(runs)
    )
    assert above <= epsilon * runs


def test_s_low_is_below_s_and_tightens_with_rounds() -> None:
    rng = np.random.default_rng(8)
    small = chsh.estimate(quantum_counts(500, rng))
    large = chsh.estimate(quantum_counts(50_000, rng))
    assert small.lower_bound(1e-6) < small.s
    assert small.s - small.lower_bound(1e-6) > large.s - large.lower_bound(1e-6)
    # With 200,000 rounds of an ideal pair, S_low at ε = 2⁻³² still clears 2.
    assert large.lower_bound(2**-32) > 2


def test_estimate_refuses_missing_settings() -> None:
    with pytest.raises(ValueError, match="all four setting pairs"):
        chsh.estimate({(0, 0): {"00": 1}})
    with pytest.raises(ValueError, match="no shots"):
        chsh.estimate({setting: ({} if setting == (1, 1) else {"00": 1}) for setting in SETTINGS})
    with pytest.raises(ValueError, match="epsilon"):
        chsh.estimate({setting: {"00": 1} for setting in SETTINGS}).lower_bound(0)


def test_s_low_is_hoeffdings_bound_on_the_win_rate() -> None:
    # 750 wins in 1,000 rounds at ε = e⁻²: the margin is √(2/2000) and S_low = 8(0.75 − it) − 4.
    result = chsh.Estimate(s=2.0, standard_error=0.0, rounds=1_000, wins=750)
    assert result.lower_bound(math.exp(-2)) == pytest.approx(8 * (0.75 - math.sqrt(0.001)) - 4)
