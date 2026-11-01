import math
from collections.abc import Callable
from typing import Any

import pytest

from coin.circuit import ARITY, Circuit, Gate, Measure


def test_the_coin() -> None:
    empty = Circuit(1)
    coin = empty.h(0).measure(0, 0)
    assert coin.ops == (Gate("h", (0,)), Measure(0, 0))
    assert empty.ops == ()


def test_bell_pair() -> None:
    bell = Circuit(2).h(0).cx(0, 1).measure_all()
    assert bell.ops == (
        Gate("h", (0,)),
        Gate("cx", (0, 1)),
        Measure(0, 0),
        Measure(1, 1),
    )


def test_rotations_carry_their_angle() -> None:
    assert Circuit(1).rz(math.pi / 2, 0).ops == (Gate("rz", (0,), (math.pi / 2,)),)


@pytest.mark.parametrize("name", sorted(ARITY))
def test_every_gate_builds_with_its_arity(name: str) -> None:
    n_qubits, n_params = ARITY[name]
    gate = Gate(name, tuple(range(n_qubits)), (0.5,) * n_params)
    assert Circuit(2).append(gate).ops == (gate,)


@pytest.mark.parametrize(
    "build",
    [
        lambda: Circuit(1).h(1),
        lambda: Circuit(2).cx(0, 2),
        lambda: Circuit(1).measure(0, 1),
        lambda: Circuit(1).h(-1),
    ],
)
def test_out_of_range_index_is_rejected(build: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="outside a"):
        build()


@pytest.mark.parametrize(
    ("gate", "message"),
    [
        (lambda: Gate("h", (0, 1)), "acts on 1 qubit"),
        (lambda: Gate("cx", (0,)), "acts on 2 qubit"),
        (lambda: Gate("rz", (0,)), "takes 1 parameter"),
        (lambda: Gate("h", (0,), (1.0,)), "takes 0 parameter"),
        (lambda: Gate("cx", (1, 1)), "more than once"),
        (lambda: Gate("toffoli", (0, 1, 2)), "unknown gate"),
    ],
)
def test_malformed_gate_is_rejected(gate: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        gate()


def test_circuit_needs_a_qubit() -> None:
    with pytest.raises(ValueError, match="at least one qubit"):
        Circuit(0)


def test_circuits_are_values() -> None:
    a = Circuit(2).h(0).cx(0, 1)
    b = Circuit(2).h(0).cx(0, 1)
    assert a == b
    assert hash(a) == hash(b)
    assert a != Circuit(2).h(1).cx(0, 1)
    assert len({a, b}) == 1


@pytest.mark.parametrize("angle", [math.nan, math.inf, -math.inf])
def test_non_finite_angle_is_rejected(angle: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        Circuit(1).rx(angle, 0)


# Deliberately ill-typed, as a caller without a type checker might pass.
FLOAT_INDEX: Any = 1.0


@pytest.mark.parametrize(
    "build",
    [
        lambda: Circuit(2).h(FLOAT_INDEX),
        lambda: Circuit(2).h(True),
        lambda: Circuit(2).measure(0, FLOAT_INDEX),
        lambda: Circuit(FLOAT_INDEX + 1),
    ],
)
def test_non_integer_index_is_rejected(build: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="integer"):
        build()
