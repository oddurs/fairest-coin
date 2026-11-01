"""Gates as exact unitary matrices, in Qiskit's conventions.

Every prediction in the project rests on these matrices, so they follow Qiskit exactly and
hardware results line up without translation:

- RZ(θ) = diag(e^{-iθ/2}, e^{iθ/2}), and RX, RY likewise as e^{-iθσ/2}.
- Qubit order is little-endian. A two-qubit matrix for `Gate(name, (a, b))` acts on basis
  states |b a⟩: the first qubit listed is the least significant bit, so its matrix is
  built as `np.kron(op_on_b, op_on_a)`. For CX, `a` is the control and `b` the target.
"""

import numpy as np
import numpy.typing as npt

from coin.circuit import Gate

type Matrix = npt.NDArray[np.complex128]


def _frozen(rows: list[list[complex]]) -> Matrix:
    # Guards shared constants against an accidental `m *= 2`, not against deliberate setflags.
    m = np.array(rows, dtype=np.complex128)
    m.setflags(write=False)
    return m


_r = 1 / np.sqrt(2)

I = _frozen([[1, 0], [0, 1]])
X = _frozen([[0, 1], [1, 0]])
Y = _frozen([[0, -1j], [1j, 0]])
Z = _frozen([[1, 0], [0, -1]])
H = _frozen([[_r, _r], [_r, -_r]])
S = _frozen([[1, 0], [0, 1j]])
SDG = _frozen([[1, 0], [0, -1j]])
T = _frozen([[1, 0], [0, np.exp(1j * np.pi / 4)]])
SX = _frozen([[(1 + 1j) / 2, (1 - 1j) / 2], [(1 - 1j) / 2, (1 + 1j) / 2]])
CX = _frozen([[1, 0, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0]])
CZ = _frozen([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, -1]])


def rx(theta: float) -> Matrix:
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return _frozen([[c, -1j * s], [-1j * s, c]])


def ry(theta: float) -> Matrix:
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return _frozen([[c, -s], [s, c]])


def rz(theta: float) -> Matrix:
    return _frozen([[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]])


_FIXED: dict[str, Matrix] = {
    "i": I,
    "x": X,
    "y": Y,
    "z": Z,
    "h": H,
    "s": S,
    "sdg": SDG,
    "t": T,
    "sx": SX,
    "cx": CX,
    "cz": CZ,
}
_ROTATIONS = {"rx": rx, "ry": ry, "rz": rz}


def matrix(gate: Gate) -> Matrix:
    """The unitary for `gate`, as a read-only 2ⁿ×2ⁿ array in the module's qubit order."""
    if gate.name in _ROTATIONS:
        return _ROTATIONS[gate.name](gate.params[0])
    return _FIXED[gate.name]
