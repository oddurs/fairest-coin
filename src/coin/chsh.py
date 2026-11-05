"""The CHSH test: two entangled coins, each read along one of two angles.

Alice measures her qubit along angle a ∈ {0, π/2} and Bob along b ∈ {π/4, −π/4}, each angle
an axis in the X–Z plane. For the Bell pair (|00⟩ + |11⟩)/√2 the correlation between their
bits is E(a, b) = cos(a − b), and

    S = E(a₀, b₀) + E(a₀, b₁) + E(a₁, b₀) − E(a₁, b₁) = 2√2.

(Written with the minus sign on E(a₁, b₁); labelling the settings differently moves it, and
changes nothing.) Any pre-written list of answers, however clever, keeps |S| ≤ 2. Noise
pulls S down toward 0, so which two qubits run the test decides how far above 2 it can get.

Predicting S for a pair uses the same noise model as the one-qubit coin: relaxation and
depolarizing for every gate, including the `cz`, then each qubit's readout. The readout
should come from readout runs made in the same session, not the published calibration:
spike 0069 found published p(1|0) correlates only +0.46 with measured.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from coin.circuit import Circuit, Gate, Measure
from coin.compile import lower, zxzxz
from coin.gates import matrix
from coin.noise import (
    VIRTUAL_GATES,
    GateCalibration,
    QubitNoise,
    Readout,
    apply_readout,
    depolarizing,
    gate_depolarizing,
    model_from_calibration,
    pair_depolarizing,
    pair_gate_depolarizing,
    pair_gates,
    thermal_relaxation,
)
from coin.sim import Channel, probabilities

ALICE = (0.0, math.pi / 2)
BOB = (math.pi / 4, -math.pi / 4)
# No local hidden-variable model exceeds 2; quantum mechanics reaches 2√2 (Tsirelson).
CLASSICAL_BOUND = 2.0
TSIRELSON = 2 * math.sqrt(2)


def circuit(a: float, b: float) -> Circuit:
    """The Bell pair on virtual qubits 0 (Alice) and 1 (Bob), each read along its angle.

    RY(−θ) turns the axis at angle θ from Z toward X onto Z, so measuring Z after it reads
    that axis. Bit 0 is Alice's and bit 1 Bob's.
    """
    return Circuit(2).h(0).cx(0, 1).ry(-a, 0).ry(-b, 1).measure(0, 0).measure(1, 1)


def lowered_circuits() -> dict[tuple[int, int], Circuit]:
    """Each setting's circuit, lowered to its shortest native form."""
    return {(i, j): lower(circuit(a, b)) for i, a in enumerate(ALICE) for j, b in enumerate(BOB)}


def setting_circuits() -> dict[tuple[int, int], Circuit]:
    """The four settings' circuits on one native skeleton, so one program can sweep them.

    The Bell pair is H on each qubit, a `cz`, and H on Bob's again; Alice then reads along
    RY(−a) and Bob along RY(−b). Everything after the `cz` is one unitary per qubit, written
    as rz·sx·rz·sx·rz whatever it is, so the four circuits differ only in `rz` angles, which
    cost nothing on hardware and can be chosen shot by shot.
    """
    prefix = lower(Circuit(2).h(0).h(1)).ops
    hadamard = matrix(Gate("h", (0,)))
    out = {}
    for i, a in enumerate(ALICE):
        for j, b in enumerate(BOB):
            alice = matrix(Gate("ry", (0,), (-a,)))
            bob = matrix(Gate("ry", (0,), (-b,))) @ hadamard
            ops = (
                *prefix,
                Gate("cz", (0, 1)),
                *zxzxz(alice, 0),
                *zxzxz(bob, 1),
                Measure(0, 0),
                Measure(1, 1),
            )
            out[i, j] = Circuit(2, ops)
    return out


def correlation(distribution: Mapping[str, float]) -> float:
    """E = P(the two bits agree) − P(they differ), for two-bit outcome strings."""
    return sum(p if outcome[0] == outcome[1] else -p for outcome, p in distribution.items())


def s_value(correlations: Mapping[tuple[int, int], float]) -> float:
    """S from the four correlations, keyed by (Alice's setting, Bob's setting)."""
    e = correlations
    return e[0, 0] + e[0, 1] + e[1, 0] - e[1, 1]


# Outcome counts for each setting pair, keyed (Alice's setting, Bob's setting), with outcome
# strings "<Bob's bit><Alice's bit>" as the circuit measures them.
type Counts = Mapping[tuple[int, int], Mapping[str, int]]


# The order a swept run numbers its settings in: choice k runs SETTINGS[k].
SETTINGS: tuple[tuple[int, int], ...] = ((0, 0), (0, 1), (1, 0), (1, 1))


def counts_by_setting(memory: Sequence[str], choices: str) -> dict[tuple[int, int], dict[str, int]]:
    """Each setting pair's outcome counts from a swept run's shots and the choice behind each.

    `choices` holds one digit per shot, k meaning SETTINGS[k], as the archive keeps it.
    """
    if len(memory) != len(choices):
        raise ValueError(f"{len(memory)} shots but {len(choices)} choices")
    counts: dict[tuple[int, int], dict[str, int]] = {setting: {} for setting in SETTINGS}
    for outcome, k in zip(memory, choices, strict=True):
        tally = counts[SETTINGS[int(k)]]
        tally[outcome] = tally.get(outcome, 0) + 1
    return counts


@dataclass(frozen=True)
class Estimate:
    """S from a run's counts, its standard error, and the CHSH game's tally behind the bound.

    The standard error describes the scatter of S over repeated runs; it is not a soundness
    bound, and S − 5σ is not a certificate. `lower_bound` is.
    """

    s: float
    standard_error: float
    rounds: int
    wins: int

    def lower_bound(self, epsilon: float) -> float:
        """A value S is above, unless a probability-ε accident happened: S_low at ε.

        Each round is a game won when the bits agree, except at settings (1, 1) where they
        must differ. With settings drawn uniformly, the win probability is w = 1/2 + S/8,
        and Hoeffding's inequality bounds w from the n rounds without assuming anything about
        their distribution but independence: P(ŵ − w ≥ t) ≤ e^{−2nt²}. So
        S_low = 8·(ŵ − √(ln(1/ε)/2n)) − 4.
        """
        if not 0 < epsilon < 1:
            raise ValueError(f"epsilon must lie in (0, 1), got {epsilon}")
        margin = math.sqrt(math.log(1 / epsilon) / (2 * self.rounds))
        return 8 * (self.wins / self.rounds - margin) - 4


def correlations_by_setting(counts: Counts) -> dict[tuple[int, int], float]:
    """Each setting's correlation E = P(agree) − P(differ) from its counts."""
    out = {}
    for setting, outcomes in counts.items():
        n = sum(outcomes.values())
        if n < 1:
            raise ValueError(f"settings {setting} have no shots")
        agree = sum(k for outcome, k in outcomes.items() if outcome[0] == outcome[1])
        out[setting] = (2 * agree - n) / n
    return out


def estimate(counts: Counts) -> Estimate:
    """S and its standard error from the four settings' counts, and the game's tally.

    Each correlation E = P(agree) − P(differ) is a binomial estimate with variance
    (1 − E²)/n from its own n shots, and the four are independent, so their variances add.
    """
    if set(counts) != {(i, j) for i in (0, 1) for j in (0, 1)}:
        raise ValueError(f"need counts for all four setting pairs, got {sorted(counts)}")
    correlations, variance, rounds, wins = {}, 0.0, 0, 0
    for (i, j), outcomes in counts.items():
        n = sum(outcomes.values())
        if n < 1:
            raise ValueError(f"settings ({i}, {j}) have no shots")
        agree = sum(k for outcome, k in outcomes.items() if outcome[0] == outcome[1])
        e = (2 * agree - n) / n
        correlations[i, j] = e
        variance += (1 - e * e) / n
        rounds += n
        wins += n - agree if (i, j) == (1, 1) else agree
    return Estimate(s_value(correlations), math.sqrt(variance), rounds, wins)


@dataclass(frozen=True)
class PairScore:
    """A coupled pair, Alice's qubit first, and the S the noise model predicts for it."""

    pair: tuple[int, int]
    s: float
    cz_error: float
    # Where each qubit's readout error came from: "measured" or "published".
    readout_source: tuple[str, str]


def predict_distribution(
    alice: QubitNoise,
    bob: QubitNoise,
    cz: GateCalibration,
    readout: tuple[Readout, Readout],
    circuit: Circuit,
) -> dict[str, float]:
    """What a native two-qubit circuit reads out on these two qubits.

    Relaxation and depolarizing follow every gate, the `cz`'s sized for four dimensions;
    then each qubit's bit is misread by its readout. Virtual qubit 0 is Alice's, 1 Bob's.
    """
    noise = (alice, bob)

    def channels(op: Gate | Measure) -> tuple[Channel, ...]:
        if isinstance(op, Measure) or op.name in VIRTUAL_GATES:
            return ()
        if op.name == "cz":
            relaxation = tuple(
                thermal_relaxation(noise[q].t1_ns, noise[q].t2_ns, cz.length_ns, q) for q in (0, 1)
            )
            p = pair_gate_depolarizing(cz.error, (relaxation[0], relaxation[1]))
            return (*relaxation[0], *relaxation[1], pair_depolarizing(p, (0, 1)))
        (q,) = op.qubits
        cal = noise[q].gates[op.name]
        relaxation = thermal_relaxation(noise[q].t1_ns, noise[q].t2_ns, cal.length_ns, q)
        return (*relaxation, depolarizing(gate_depolarizing(cal.error, relaxation), q))

    true = probabilities(circuit, channels)
    return apply_readout(true, {0: readout[0], 1: readout[1]})


def predict_s(
    alice: QubitNoise,
    bob: QubitNoise,
    cz: GateCalibration,
    readout: tuple[Readout, Readout],
    circuits: Mapping[tuple[int, int], Circuit] | None = None,
) -> float:
    """S for the CHSH test on these two qubits, from their noise and readout.

    `circuits` are the four settings' native circuits, the shortest lowering by default;
    a per-shot sweep runs `setting_circuits` instead, which has more pulses.
    """
    correlations = {
        setting: correlation(predict_distribution(alice, bob, cz, readout, native))
        for setting, native in (circuits or lowered_circuits()).items()
    }
    return s_value(correlations)


def rank_pairs(
    calibration: dict[str, Any], measured: Mapping[int, Readout] | None = None
) -> list[PairScore]:
    """Every usable coupled pair, best predicted S first.

    Only pairs the calibration couples with a `cz` are scored; nothing is routed. A pair is
    left out if either qubit's calibration is unusable or its `cz` is marked failed. Each
    qubit's readout is `measured[q]` where given, else the published value.
    """
    model = model_from_calibration(calibration)
    measured = measured or {}
    scores = []
    # The pairs with a usable cz are exactly the coupled ones the chip can run.
    for pair, cz in sorted(pair_gates(calibration).items()):
        a, b = pair
        if a not in model.qubits or b not in model.qubits:
            continue
        readout = tuple(measured.get(q, model.qubits[q].readout) for q in pair)
        source = tuple("measured" if q in measured else "published" for q in pair)
        s = predict_s(model.qubits[a], model.qubits[b], cz, (readout[0], readout[1]))
        scores.append(PairScore(pair, s, cz.error, (source[0], source[1])))
    return sorted(scores, key=lambda score: (-score.s, score.pair))
