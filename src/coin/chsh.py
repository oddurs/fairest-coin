"""The CHSH test: two entangled coins, each read along one of two angles.

Alice measures her qubit along angle a ∈ {0, π/2} and Bob along b ∈ {π/4, −π/4}, each angle
an axis in the X–Z plane. For the Bell pair (|00⟩ + |11⟩)/√2 the correlation between their
bits is E(a, b) = cos(a − b), and

    S = E(a₀, b₀) + E(a₀, b₁) + E(a₁, b₀) − E(a₁, b₁) = 2√2.

Any pre-written list of answers, however clever, keeps |S| ≤ 2. Noise pulls S down toward
0, so which two qubits run the test decides how far above 2 it can get.

Predicting S for a pair uses the same noise model as the one-qubit coin: relaxation and
depolarizing for every gate, including the `cz`, then each qubit's readout. The readout
should come from readout runs made in the same session, not the published calibration:
spike 0069 found published p(1|0) correlates only +0.46 with measured.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from coin.circuit import Circuit, Gate, Measure
from coin.compile import lower
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


def correlation(distribution: Mapping[str, float]) -> float:
    """E = P(the two bits agree) − P(they differ), for two-bit outcome strings."""
    return sum(p if outcome[0] == outcome[1] else -p for outcome, p in distribution.items())


def s_value(correlations: Mapping[tuple[int, int], float]) -> float:
    """S from the four correlations, keyed by (Alice's setting, Bob's setting)."""
    e = correlations
    return e[0, 0] + e[0, 1] + e[1, 0] - e[1, 1]


@dataclass(frozen=True)
class PairScore:
    """A coupled pair, Alice's qubit first, and the S the noise model predicts for it."""

    pair: tuple[int, int]
    s: float
    cz_error: float
    # Where each qubit's readout error came from: "measured" or "published".
    readout_source: tuple[str, str]


def predict_s(
    alice: QubitNoise, bob: QubitNoise, cz: GateCalibration, readout: tuple[Readout, Readout]
) -> float:
    """S for the CHSH test on these two qubits, from their noise and readout."""
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

    correlations = {}
    for i, a in enumerate(ALICE):
        for j, b in enumerate(BOB):
            true = probabilities(lower(circuit(a, b)), channels)
            read = apply_readout(true, {0: readout[0], 1: readout[1]})
            correlations[i, j] = correlation(read)
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
