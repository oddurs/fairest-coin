"""How real qubits go wrong: noise channels as Kraus operators, and readout as a classical map.

Two kinds of error, kept apart on purpose:

- Quantum channels act on the state ρ, before it is measured: a qubit relaxes from |1⟩ to |0⟩
  (amplitude damping, T1), loses its phase (dephasing, T2), or is scrambled by an imperfect
  gate (depolarizing). These are `Channel`s for the density-matrix simulator.
- Readout error happens after the state is gone: the measurement reports the wrong bit. It
  acts on outcome probabilities, never on ρ, so it is a `Readout` applied to a distribution.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from coin.circuit import Circuit, Gate, Measure
from coin.sim import Channel, probabilities


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


# ─── From a backend's calibration to a per-qubit noise model ─────────────────────────────

# Spike 0018: readout asymmetry dominates a one-gate coin, decay during gates is ~40× smaller,
# and decay during the measurement window is already inside IBM's readout calibration.
REQUIRED_QUBIT_FIELDS = ("T1", "T2", "prob_meas1_prep0", "prob_meas0_prep1")
# The timed native gates a lowered single-qubit circuit uses; sx is required, x optional.
TIMED_GATES = ("sx", "x")
# IBM reports a failed calibration as gate_error = 1, and a readout error of one half or more
# is no better than guessing. Neither is a measurement the model can use.
BROKEN = 0.5
# rz is a frame change on IBM hardware: it takes no time and adds no error.
VIRTUAL_GATES = frozenset({"rz"})
_NANOSECONDS = {"ns": 1.0, "us": 1e3, "µs": 1e3, "ms": 1e6, "s": 1e9}


@dataclass(frozen=True)
class GateCalibration:
    length_ns: float
    error: float


@dataclass(frozen=True)
class QubitNoise:
    """Everything the model knows about one physical qubit, in nanoseconds."""

    t1_ns: float
    t2_ns: float
    readout: Readout
    readout_length_ns: float | None
    gates: Mapping[str, GateCalibration]


@dataclass(frozen=True)
class CalibrationModel:
    """Noise for every usable qubit, and why every other qubit was left out."""

    qubits: Mapping[int, QubitNoise]
    excluded: Mapping[int, str]


def model_from_calibration(calibration: Any) -> CalibrationModel:
    """Build a per-qubit noise model from an IBM `backend.properties().to_dict()` snapshot.

    Every problem with one qubit (a missing or nonsensical field, an unknown unit, a gate IBM
    marks as failed, T2 > 2·T1) excludes that qubit with its reason, never a default: a
    guessed number would be a prediction the hardware could not test. Content that is not a
    snapshot at all raises ValueError.
    """
    if not (
        isinstance(calibration, Mapping)
        and isinstance(calibration.get("qubits"), list)
        and isinstance(calibration.get("gates"), list)
    ):
        raise ValueError("not a calibration snapshot: expected an object with qubits and gates")

    timed: dict[int, dict[str, list[Mapping[str, Any]]]] = {}
    for gate in calibration["gates"]:
        if gate.get("gate") in TIMED_GATES and len(gate.get("qubits", [])) == 1:
            timed.setdefault(gate["qubits"][0], {}).setdefault(gate["gate"], []).append(gate)

    qubits: dict[int, QubitNoise] = {}
    excluded: dict[int, str] = {}
    for q, props in enumerate(calibration["qubits"]):
        try:
            qubits[q] = _qubit_noise(props, timed.get(q, {}))
        except _UnusableError as reason:
            excluded[q] = str(reason)
    return CalibrationModel(qubits, excluded)


class _UnusableError(Exception):
    """Why one qubit's calibration cannot be used."""


def _qubit_noise(
    props: list[Mapping[str, Any]], gates: Mapping[str, list[Mapping[str, Any]]]
) -> QubitNoise:
    fields = {p["name"]: p for p in props}
    if missing := [name for name in REQUIRED_QUBIT_FIELDS if name not in fields]:
        raise _UnusableError(f"missing {', '.join(missing)}")
    t1, t2 = _in_ns(fields["T1"]), _in_ns(fields["T2"])
    for name, value in (("T1", t1), ("T2", t2)):
        if not (math.isfinite(value) or value == math.inf) or value <= 0:
            raise _UnusableError(f"{name} = {value} is not a positive time")
    if t2 > 2 * t1:
        raise _UnusableError(f"T2 = {t2 / 1e3:.2f} µs exceeds 2·T1 = {2 * t1 / 1e3:.2f} µs")
    readout = tuple(_number(fields[name]) for name in ("prob_meas1_prep0", "prob_meas0_prep1"))
    if not all(0 <= p < BROKEN for p in readout):
        raise _UnusableError(f"readout error {readout} is no better than guessing")

    calibrated: dict[str, GateCalibration] = {}
    for name, entries in gates.items():
        if len(entries) > 1:
            raise _UnusableError(f"duplicate {name} calibration")
        params = {p["name"]: p for p in entries[0]["parameters"]}
        if "gate_length" not in params or "gate_error" not in params:
            raise _UnusableError(f"{name} calibration lacks gate_length or gate_error")
        error = _number(params["gate_error"])
        if not 0 <= error < BROKEN:
            raise _UnusableError(f"{name} gate_error = {error} marks a failed calibration")
        calibrated[name] = GateCalibration(_in_ns(params["gate_length"]), error)
    if "sx" not in calibrated:
        raise _UnusableError("no sx calibration")

    length = fields.get("readout_length")
    return QubitNoise(
        t1_ns=t1,
        t2_ns=t2,
        readout=Readout(readout[0], readout[1]),
        readout_length_ns=None if length is None else _in_ns(length),
        gates=calibrated,
    )


def predict_tails(noise: QubitNoise, circuit: Circuit, *, measurement_decay: bool = False) -> float:
    """P(tails) for a one-qubit circuit, measured into classical bit 0, on this qubit.

    The circuit must already be in the hardware's native gates; anything without a
    calibrated duration raises rather than being treated as free. `measurement_decay`
    adds T1/T2 over the readout window: the double-counting alternative spike 0018 rejected,
    kept so hardware can settle the question.
    """
    if circuit.n_qubits != 1:
        raise ValueError(f"predict_tails takes a one-qubit circuit, got {circuit.n_qubits}")

    def channels(op: Gate | Measure) -> tuple[Channel, ...]:
        if isinstance(op, Measure):
            if not measurement_decay:
                return ()
            if noise.readout_length_ns is None:
                raise ValueError("measurement decay needs readout_length, which is missing")
            return thermal_relaxation(noise.t1_ns, noise.t2_ns, noise.readout_length_ns, 0)
        if op.name in VIRTUAL_GATES:
            return ()
        if op.name not in noise.gates:
            raise ValueError(
                f"no calibration for gate {op.name}; lower the circuit to native gates first"
            )
        cal = noise.gates[op.name]
        # IBM reports average gate error r; for one qubit, depolarizing p = 2r.
        return (
            *thermal_relaxation(noise.t1_ns, noise.t2_ns, cal.length_ns, 0),
            depolarizing(min(1.0, 2 * cal.error), 0),
        )

    true = probabilities(circuit, channels)
    return apply_readout(true, {0: noise.readout}).get("1", 0.0)


def _number(field: Mapping[str, Any]) -> float:
    value = field.get("value")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _UnusableError(f"{field.get('name')} = {value!r} is not a number")
    return float(value)


def _in_ns(field: Mapping[str, Any]) -> float:
    unit = field.get("unit", "")
    if unit not in _NANOSECONDS:
        raise _UnusableError(f"{field.get('name')} has unknown time unit {unit!r}")
    return _number(field) * _NANOSECONDS[unit]
