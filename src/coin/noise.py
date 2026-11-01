"""How real qubits go wrong: noise channels as Kraus operators, and readout as a classical map.

Two kinds of error, kept apart on purpose:

- Quantum channels act on the state ρ, before it is measured: a qubit relaxes from |1⟩ to |0⟩
  (amplitude damping, T1), loses its phase (dephasing, T2), or is scrambled by an imperfect
  gate (depolarizing). These are `Channel`s for the density-matrix simulator.
- Readout error happens after the state is gone: the measurement reports the wrong bit. It
  acts on outcome probabilities, never on ρ, so it is a `Readout` applied to a distribution.
"""

import math
from dataclasses import dataclass

import numpy as np

from coin.sim import Channel


def _check_probability(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be a probability in [0, 1], got {value}")


def amplitude_damping(gamma: float, qubit: int) -> Channel:
    """|1⟩ decays to |0⟩ with probability `gamma`: the energy loss behind T1."""
    _check_probability("gamma", gamma)
    k0 = np.array([[1, 0], [0, math.sqrt(1 - gamma)]], dtype=np.complex128)
    k1 = np.array([[0, math.sqrt(gamma)], [0, 0]], dtype=np.complex128)
    return Channel((k0, k1), (qubit,))


def phase_damping(lam: float, qubit: int) -> Channel:
    """Coherence between |0⟩ and |1⟩ shrinks by √(1-λ); populations are untouched."""
    _check_probability("lambda", lam)
    k0 = np.array([[1, 0], [0, math.sqrt(1 - lam)]], dtype=np.complex128)
    k1 = np.array([[0, 0], [0, math.sqrt(lam)]], dtype=np.complex128)
    return Channel((k0, k1), (qubit,))


def thermal_relaxation(t1: float, t2: float, duration: float, qubit: int) -> tuple[Channel, ...]:
    """What `duration` of idling does to a qubit with relaxation time T1 and coherence time T2.

    Amplitude damping alone already decays coherence as e^{-t/2T1}; the rest of the e^{-t/T2}
    decay is pure dephasing with 1/Tφ = 1/T2 - 1/(2·T1). That rate is negative, and the model
    unphysical, when T2 > 2·T1. Times share whatever unit the caller uses.
    """
    if t1 <= 0 or t2 <= 0 or duration < 0:
        raise ValueError(f"need T1, T2 > 0 and duration ≥ 0, got {t1}, {t2}, {duration}")
    if t2 > 2 * t1:
        raise ValueError(f"T2 = {t2} exceeds 2·T1 = {2 * t1}, which no physical qubit allows")
    gamma = 1 - math.exp(-duration / t1)
    pure_dephasing_rate = 1 / t2 - 1 / (2 * t1)
    # Phase damping scales coherence by √(1-λ); we need e^{-t/Tφ}, so 1-λ = e^{-2t/Tφ}.
    lam = 1 - math.exp(-2 * duration * pure_dephasing_rate)
    return amplitude_damping(gamma, qubit), phase_damping(lam, qubit)


def depolarizing(p: float, qubit: int) -> Channel:
    """ρ → (1-p)·ρ + p·I/2, Qiskit's convention: with probability p the qubit is scrambled."""
    _check_probability("p", p)
    paulis = (
        np.array([[0, 1], [1, 0]], dtype=np.complex128),
        np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        np.array([[1, 0], [0, -1]], dtype=np.complex128),
    )
    identity = math.sqrt(1 - 3 * p / 4) * np.eye(2, dtype=np.complex128)
    return Channel((identity, *(math.sqrt(p / 4) * pauli for pauli in paulis)), (qubit,))


@dataclass(frozen=True)
class Readout:
    """A measurement that misreports: P(read 1 | was 0) and P(read 0 | was 1).

    Usually asymmetric, since a |1⟩ can also decay during the measurement window.
    """

    p1_given_0: float
    p0_given_1: float

    def __post_init__(self) -> None:
        _check_probability("p1_given_0", self.p1_given_0)
        _check_probability("p0_given_1", self.p0_given_1)


def apply_readout(probabilities: dict[str, float], errors: dict[int, Readout]) -> dict[str, float]:
    """The outcome distribution a faulty measurement reports, given the true one.

    `errors` maps classical bit → its readout error; each bit is misread independently.
    Outcome strings have classical bit 0 on the right, as everywhere in the project.
    """
    result = dict(probabilities)
    for clbit, error in errors.items():
        flipped: dict[str, float] = {}
        for outcome, p in result.items():
            position = len(outcome) - 1 - clbit
            if position < 0:
                raise ValueError(f"classical bit {clbit} is not in outcome {outcome!r}")
            bit = outcome[position]
            p_flip = error.p1_given_0 if bit == "0" else error.p0_given_1
            other = outcome[:position] + ("1" if bit == "0" else "0") + outcome[position + 1 :]
            flipped[outcome] = flipped.get(outcome, 0.0) + p * (1 - p_flip)
            flipped[other] = flipped.get(other, 0.0) + p * p_flip
        result = flipped
    return {outcome: p for outcome, p in result.items() if p > 0}
