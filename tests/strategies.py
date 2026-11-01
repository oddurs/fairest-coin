"""Hypothesis strategies shared by the simulator and density-matrix tests."""

import numpy as np
from hypothesis import strategies as st

from coin.circuit import ARITY, Circuit, Gate


@st.composite
def gates(draw: st.DrawFn, n_qubits: int) -> Gate:
    names = [name for name, (k, _) in ARITY.items() if k <= n_qubits]
    name = draw(st.sampled_from(sorted(names)))
    k, n_params = ARITY[name]
    qubits = draw(st.permutations(range(n_qubits)))[:k]
    angle = st.floats(min_value=-2 * np.pi, max_value=2 * np.pi, allow_nan=False)
    params = tuple(draw(angle) for _ in range(n_params))
    return Gate(name, tuple(qubits), params)


@st.composite
def circuits(draw: st.DrawFn, max_qubits: int) -> Circuit:
    n = draw(st.integers(min_value=1, max_value=max_qubits))
    ops = draw(st.lists(gates(n), max_size=20))
    return Circuit(n, tuple(ops))
