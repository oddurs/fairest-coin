"""Lowering circuits to the gates IBM hardware runs, and writing them as OpenQASM 3.

IBM's Heron backends run `rz`, `sx`, `x` and `cz` natively and nothing else. `lower`
rewrites every gate into that set: each run of consecutive single-qubit gates on a qubit is
multiplied into one 2×2 unitary, which becomes at most rz·sx·rz·sx·rz (the ZXZXZ form),
shortened where the unitary allows. A `cx` becomes one `cz` between Hadamards on its
target, and those Hadamards join the runs either side, so the Bell circuit's H, CX costs
one `cz` and no more pulses than it must.

The hardware has a fixed set of coupled pairs, and a two-qubit gate can only run on one of
them. `require_coupled` refuses any other pair rather than routing it: routing would insert
SWAPs, three more `cz` each, and the circuit run would not be the circuit written.

Equality is up to global phase, which no measurement can see. `rz` is free on hardware (a
frame change in the control electronics, not a pulse), so the shortening that matters is
dropping `sx` pulses; dropping an `rz` just keeps the program readable.

The QASM addresses a virtual register `q[0..n-1]`. Which physical qubit each one lands on is
not part of the program: the hardware adapter passes the layout to Qiskit's transpiler as
`initial_layout`, with `optimization_level=0` so the native gates pass through untouched.
"""

import cmath
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from coin.circuit import ARITY, Circuit, Gate, Measure, Op
from coin.gates import Matrix, matrix

NATIVE: frozenset[str] = frozenset({"rz", "sx", "x", "cz"})

# Where a decomposition angle is this close to a shorter form, take the shorter form. Snapping
# moves the unitary by at most about SNAP/2 per snap, so it only catches rounding residue
# (≈1e-15 after merging a run of gates), never a rotation anyone asked for.
SNAP = 1e-12

_H = matrix(Gate("h", (0,)))


def lower(circuit: Circuit) -> Circuit:
    """`circuit` rewritten in native `rz`, `sx`, `x` and `cz`.

    Consecutive single-qubit gates on a qubit merge into one unitary before lowering, so
    gate counts may shrink. Each `cx` becomes one `cz`, since CX = (I⊗H)·CZ·(I⊗H) with the
    Hadamards on the target. Two-qubit gates and measurements stay in place and keep their
    order relative to the gates on the qubits they touch. The result equals `circuit` up to
    global phase.
    """
    pending: dict[int, Matrix] = {}
    ops: list[Op] = []

    def flush(qubits: tuple[int, ...]) -> None:
        for q in qubits:
            if q in pending:
                ops.extend(_lower_unitary(pending.pop(q), q))

    for op in circuit.ops:
        if isinstance(op, Measure):
            flush((op.qubit,))
            ops.append(op)
        elif ARITY[op.name][0] == 1:
            q = op.qubits[0]
            pending[q] = matrix(op) @ pending.get(q, np.eye(2, dtype=np.complex128))
        elif op.name == "cx":
            # The Hadamard before joins the target's run so far; the one after starts its
            # next run, so both merge with whatever surrounds them.
            target = op.qubits[1]
            pending[target] = _H @ pending.get(target, np.eye(2, dtype=np.complex128))
            flush(op.qubits)
            ops.append(Gate("cz", op.qubits))
            pending[target] = _H.copy()
        else:
            flush(op.qubits)
            ops.append(op)
    flush(tuple(sorted(pending)))
    return Circuit(circuit.n_qubits, tuple(ops))


def coupled_pairs(calibration: dict[str, Any]) -> frozenset[frozenset[int]]:
    """The physical qubit pairs a backend's calibration lists its native `cz` on."""
    return frozenset(
        frozenset(gate["qubits"])
        for gate in calibration.get("gates", [])
        if gate.get("gate") == "cz" and len(gate.get("qubits", [])) == 2
    )


def require_coupled(
    circuit: Circuit, layout: Sequence[int], coupled: frozenset[frozenset[int]]
) -> None:
    """Raise ValueError naming both physical qubits of the first two-qubit gate whose pair
    `layout` does not place on a coupled pair. Nothing is ever routed."""
    for op in circuit.ops:
        if isinstance(op, Gate) and len(op.qubits) == 2:
            a, b = (layout[q] for q in op.qubits)
            if frozenset((a, b)) not in coupled:
                raise ValueError(
                    f"{op.name} on physical qubits {a} and {b}: they are not coupled on this "
                    "backend, and circuits are never routed; choose a coupled pair"
                )


def to_qasm(circuit: Circuit) -> str:
    """OpenQASM 3 for a lowered circuit, on a virtual register `q` and classical register `c`.

    Raises ValueError naming the first gate outside the native set, so an unlowered circuit
    can never reach hardware by accident.
    """
    return _program(circuit, {}, [])


def zxzxz(u: Matrix, q: int) -> list[Gate]:
    """`u` on qubit `q` as exactly rz·sx·rz·sx·rz, never shortened.

    Five gates where `lower` might emit fewer: circuits that must share one skeleton (the
    CHSH settings, swept by parameter) need the same gates whatever the unitary, differing
    only in their `rz` angles, which are free on hardware.
    """
    phi, theta, lam = _euler(u)
    return [
        Gate("rz", (q,), (_wrap(lam),)),
        Gate("sx", (q,)),
        Gate("rz", (q,), (_wrap(theta + math.pi),)),
        Gate("sx", (q,)),
        Gate("rz", (q,), (_wrap(phi + math.pi),)),
    ]


@dataclass(frozen=True)
class SweptProgram:
    """Several circuits as one parametrised program: the template, and each one's angles."""

    qasm: str
    values: tuple[tuple[float, ...], ...]  # one row per circuit, in the order given


def sweep_qasm(circuits: Sequence[Circuit]) -> SweptProgram:
    """One OpenQASM 3 program standing for all of `circuits`, which must differ only in their
    `rz` angles. Each angle that varies becomes an `input float[64] p<k>`, and `values[i]`
    sets them to make circuit i. Raises ValueError if anything else differs.
    """
    if not circuits:
        raise ValueError("a sweep needs at least one circuit")
    first = circuits[0]
    skeleton = [_skeleton(op) for op in first.ops]
    for c in circuits[1:]:
        if c.n_qubits != first.n_qubits or [_skeleton(op) for op in c.ops] != skeleton:
            raise ValueError("swept circuits must have the same gates, differing only in rz angles")
    angles = [[_angle(op) for op in c.ops] for c in circuits]
    varying = [k for k in range(len(first.ops)) if len({row[k] for row in angles}) > 1]
    names = {k: f"p{i}" for i, k in enumerate(varying)}
    # Only rz angles vary (the skeletons match), so no None is ever dropped here.
    values = tuple(tuple(a for a in (row[k] for k in varying) if a is not None) for row in angles)
    return SweptProgram(_program(first, names, list(names.values())), values)


def _program(circuit: Circuit, parameters: dict[int, str], inputs: list[str]) -> str:
    """OpenQASM 3 for `circuit`, with operation k's angle written as `parameters[k]`."""
    n = circuit.n_qubits
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";']
    lines += [f"input float[64] {name};" for name in inputs]
    lines += [f"qubit[{n}] q;", f"bit[{n}] c;"]
    for k, op in enumerate(circuit.ops):
        if isinstance(op, Measure):
            lines.append(f"c[{op.clbit}] = measure q[{op.qubit}];")
            continue
        if op.name not in NATIVE:
            raise ValueError(f"{op.name} is not a native gate; lower the circuit first")
        if k in parameters:
            params = f"({parameters[k]})"
        else:
            # repr round-trips a float exactly; a rounded angle would be a different gate.
            params = f"({', '.join(repr(float(p)) for p in op.params)})" if op.params else ""
        qubits = ", ".join(f"q[{q}]" for q in op.qubits)
        lines.append(f"{op.name}{params} {qubits};")
    return "\n".join(lines) + "\n"


def _skeleton(op: Op) -> tuple[object, ...]:
    """An operation less its rz angle: what swept circuits must share."""
    if isinstance(op, Measure):
        return ("measure", op.qubit, op.clbit)
    return (op.name, op.qubits, () if op.name == "rz" else op.params)


def _angle(op: Op) -> float | None:
    """The rz angle of `op`, or None for anything else."""
    return float(op.params[0]) if isinstance(op, Gate) and op.name == "rz" else None


def _euler(u: Matrix) -> tuple[float, float, float]:
    """(φ, θ, λ) with u ∝ RZ(φ)·RY(θ)·RZ(λ) and θ ∈ [0, π]."""
    # Divide out the phase so u is in SU(2): u = [[a, −b*], [b, a*]].
    v = u / cmath.sqrt(np.linalg.det(u))
    a, b = complex(v[0, 0]), complex(v[1, 0])
    # atan2 stays accurate at both ends, where arccos(|a|) would lose half the digits.
    theta = 2 * math.atan2(abs(b), abs(a))
    # a = e^{−i(φ+λ)/2}·cos(θ/2) and b = e^{i(φ−λ)/2}·sin(θ/2). An entry that vanishes leaves
    # its phase undefined, and then any value gives the same unitary.
    total = -2 * cmath.phase(a)  # φ + λ
    diff = 2 * cmath.phase(b)  # φ − λ
    return (total + diff) / 2, theta, (total - diff) / 2


def _lower_unitary(u: Matrix, q: int) -> list[Gate]:
    """Native gates on qubit `q` whose product equals `u` up to global phase.

    Writes u ∝ RZ(φ)·RY(θ)·RZ(λ) with θ ∈ [0, π], then uses RY(θ) = RZ(π/2)·RX(θ)·RZ(−π/2)
    and SX ∝ RX(π/2) to pick the shortest native form for θ.
    """
    phi, theta, lam = _euler(u)
    if theta < SNAP:
        # Diagonal: RZ(φ)·RZ(λ).
        return _rz(phi + lam, q)
    if theta > math.pi - SNAP:
        # Antidiagonal: RY(π) ∝ X·RZ(π), and RZ(φ)·X = X·RZ(−φ), so u ∝ X·RZ(π + λ − φ).
        return [*_rz(math.pi - (phi - lam), q), Gate("x", (q,))]
    if abs(theta - math.pi / 2) < SNAP:
        # RZ(φ)·RZ(π/2)·SX·RZ(−π/2)·RZ(λ).
        return [*_rz(lam - math.pi / 2, q), Gate("sx", (q,)), *_rz(phi + math.pi / 2, q)]
    # RX(θ) ∝ RZ(π/2)·SX·RZ(θ+π)·SX·RZ(π/2), from RX = H·RZ·H and H ∝ RZ(π/2)·SX·RZ(π/2).
    return [
        *_rz(lam, q),
        Gate("sx", (q,)),
        *_rz(theta + math.pi, q),
        Gate("sx", (q,)),
        *_rz(phi + math.pi, q),
    ]


def _wrap(angle: float) -> float:
    """An rz angle in (−π, π]: RZ(α + 2π) = −RZ(α), the same gate up to global phase."""
    wrapped = math.remainder(angle, 2 * math.pi)
    return wrapped + 2 * math.pi if wrapped <= -math.pi else wrapped


def _rz(angle: float, q: int) -> list[Gate]:
    """RZ(angle) on `q`, with the angle in (−π, π], or nothing if it is the identity."""
    wrapped = _wrap(angle)
    if abs(wrapped) < SNAP:
        return []
    return [Gate("rz", (q,), (wrapped,))]
