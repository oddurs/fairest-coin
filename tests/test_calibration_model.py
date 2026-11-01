import math
from pathlib import Path
from typing import Any

import pytest

from coin.archive import load_run
from coin.circuit import Circuit
from coin.noise import Readout, model_from_calibration, predict_tails

EXACT = 1e-12
FIRST_RUN = Path(__file__).resolve().parent.parent / "data/runs/2026-11-01-dbjsk29ffo6c73baaosg"

# H lowered to IBM's native gates, as the hardware runs it.
NATIVE_COIN = Circuit(1).rz(math.pi / 2, 0).sx(0).rz(math.pi / 2, 0).measure(0, 0)


def field(name: str, value: float, unit: str = "") -> dict[str, Any]:
    return {"name": name, "value": value, "unit": unit}


def qubit(
    *,
    t1_us: float = 150.0,
    t2_us: float = 100.0,
    readout: tuple[float, float] = (0.01, 0.02),
    readout_ns: float = 2000.0,
    drop: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    p1_given_0, p0_given_1 = readout
    fields = [
        field("T1", t1_us, "us"),
        field("T2", t2_us, "us"),
        field("prob_meas1_prep0", p1_given_0),
        field("prob_meas0_prep1", p0_given_1),
        field("readout_length", readout_ns, "ns"),
    ]
    return [f for f in fields if f["name"] not in drop]


def sx(q: int, length_ns: float = 36.0, error: float = 2e-4) -> dict[str, Any]:
    return {
        "gate": "sx",
        "qubits": [q],
        "parameters": [field("gate_error", error), field("gate_length", length_ns, "ns")],
    }


def calibration(qubits: list[list[dict[str, Any]]], gates: list[dict[str, Any]]) -> dict[str, Any]:
    return {"qubits": qubits, "gates": gates}


def test_a_qubit_without_errors_predicts_exactly_half() -> None:
    perfect = calibration(
        [qubit(t1_us=math.inf, t2_us=math.inf, readout=(0.0, 0.0))],
        [sx(0, error=0.0)],
    )
    noise = model_from_calibration(perfect).qubits[0]
    assert predict_tails(noise, NATIVE_COIN) == pytest.approx(0.5, abs=EXACT)


def test_readout_alone_gives_the_closed_form() -> None:
    # A zero-length, error-free gate leaves only readout: P(1) = ½(1 − P(0|1)) + ½·P(1|0).
    cal = calibration([qubit(readout=(0.03, 0.08))], [sx(0, 0.0, 0.0)])
    noise = model_from_calibration(cal).qubits[0]
    assert predict_tails(noise, NATIVE_COIN) == pytest.approx(0.5 * 0.92 + 0.5 * 0.03, abs=EXACT)


def test_gate_decay_pushes_the_coin_towards_heads() -> None:
    cal = calibration([qubit(t1_us=10.0, t2_us=10.0, readout=(0.0, 0.0))], [sx(0, 500.0, 0.0)])
    assert predict_tails(model_from_calibration(cal).qubits[0], NATIVE_COIN) < 0.5


def test_measurement_decay_is_an_explicit_alternative() -> None:
    noise = model_from_calibration(calibration([qubit()], [sx(0)])).qubits[0]
    assert predict_tails(noise, NATIVE_COIN, measurement_decay=True) < predict_tails(
        noise, NATIVE_COIN
    )


@pytest.mark.parametrize("dropped", [("T1",), ("T2",), ("prob_meas1_prep0", "prob_meas0_prep1")])
def test_missing_fields_are_reported_not_defaulted(dropped: tuple[str, ...]) -> None:
    model = model_from_calibration(calibration([qubit(), qubit(drop=dropped)], [sx(0), sx(1)]))
    assert set(model.qubits) == {0}
    for name in dropped:
        assert name in model.excluded[1]


def test_t2_beyond_twice_t1_is_excluded_with_its_reason() -> None:
    model = model_from_calibration(calibration([qubit(t1_us=50.0, t2_us=120.0)], [sx(0)]))
    assert model.qubits == {}
    assert "exceeds 2·T1" in model.excluded[0]


def test_units_are_converted_and_unknown_units_exclude_the_qubit() -> None:
    noise = model_from_calibration(calibration([qubit(t1_us=150.0)], [sx(0)])).qubits[0]
    assert noise.t1_ns == pytest.approx(150_000.0, abs=EXACT)
    assert noise.readout == Readout(0.01, 0.02)
    furlongs = calibration([qubit()], [sx(0)])
    furlongs["qubits"][0][0]["unit"] = "furlongs"
    assert "unknown time unit" in excluded_reason(furlongs)


def test_a_gate_without_calibration_is_an_error_not_free() -> None:
    noise = model_from_calibration(calibration([qubit()], [sx(0)])).qubits[0]
    with pytest.raises(ValueError, match="lower the circuit"):
        predict_tails(noise, Circuit(1).h(0).measure(0, 0))


def test_only_one_qubit_circuits_are_predicted() -> None:
    noise = model_from_calibration(calibration([qubit()], [sx(0)])).qubits[0]
    with pytest.raises(ValueError, match="one-qubit"):
        predict_tails(noise, Circuit(2).measure_all())


def test_the_archived_snapshot_excludes_exactly_the_flagged_qubits() -> None:
    model = model_from_calibration(load_run(FIRST_RUN).calibration)
    # Spike 0018: 82, 94, 130 lack T1 or T2; 20 and 83 report T2 > 2·T1. Review of 0021: IBM
    # marks 113's sx as failed (gate_error = 1), and 119 misreads a prepared 1 54% of the time.
    assert set(model.excluded) == {20, 82, 83, 94, 113, 119, 130}
    assert len(model.qubits) == 149


def test_the_first_runs_qubit_matches_its_archived_prediction() -> None:
    run = load_run(FIRST_RUN)
    noise = model_from_calibration(run.calibration).qubits[139]
    assert run.prediction is not None
    readout_only = run.prediction.values["p_tails"]
    # The model adds decay and error during the 36 ns sx, worth ~1e-4 against readout alone.
    assert predict_tails(noise, NATIVE_COIN) == pytest.approx(readout_only, abs=5e-4)


def excluded_reason(cal: dict[str, Any], q: int = 0) -> str:
    model = model_from_calibration(cal)
    assert q not in model.qubits
    return model.excluded[q]


def test_a_gate_ibm_marks_as_failed_excludes_the_qubit() -> None:
    # IBM reports gate_error = 1 as a placeholder for a calibration that failed.
    assert "failed" in excluded_reason(calibration([qubit()], [sx(0, error=1.0)]))


def test_readout_worse_than_a_coin_excludes_the_qubit() -> None:
    assert "readout" in excluded_reason(calibration([qubit(readout=(0.01, 0.54))], [sx(0)]))


@pytest.mark.parametrize("t1_us", [math.nan, -5.0, 0.0])
def test_nonsense_t1_excludes_the_qubit(t1_us: float) -> None:
    assert "T1" in excluded_reason(calibration([qubit(t1_us=t1_us)], [sx(0)]))


def test_a_bad_unit_excludes_only_its_qubit() -> None:
    cal = calibration([qubit(), qubit()], [sx(0), sx(1)])
    cal["qubits"][1][0]["unit"] = ""
    model = model_from_calibration(cal)
    assert set(model.qubits) == {0}
    assert "unit" in model.excluded[1]


def test_a_gate_the_model_never_uses_cannot_break_it() -> None:
    odd = {"gate": "xslow", "qubits": [0], "parameters": [field("gate_length", 7, "dt")]}
    assert set(model_from_calibration(calibration([qubit()], [sx(0), odd])).qubits) == {0}


def test_a_qubit_without_sx_calibration_is_excluded() -> None:
    assert "sx" in excluded_reason(calibration([qubit()], []))


def test_duplicate_gate_calibration_excludes_the_qubit() -> None:
    assert "duplicate" in excluded_reason(calibration([qubit()], [sx(0), sx(0, error=5e-4)]))


def test_readout_length_is_only_needed_for_measurement_decay() -> None:
    noise = model_from_calibration(calibration([qubit(drop=("readout_length",))], [sx(0)])).qubits[
        0
    ]
    predict_tails(noise, NATIVE_COIN)
    with pytest.raises(ValueError, match="readout_length"):
        predict_tails(noise, NATIVE_COIN, measurement_decay=True)


@pytest.mark.parametrize("bad", [[], {"qubits": []}, {"gates": []}])
def test_content_that_is_not_a_snapshot_is_refused(bad: Any) -> None:
    with pytest.raises(ValueError, match="not a calibration snapshot"):
        model_from_calibration(bad)


def test_depolarizing_uses_twice_the_reported_gate_error() -> None:
    # sx·sx takes |0⟩ to |1⟩. Each depolarizing p shrinks the Bloch vector by (1 − p), so with
    # no other error P(1) = (1 + (1 − p)²)/2, with p = 2r for IBM's average gate error r.
    r = 0.01
    perfect = qubit(t1_us=math.inf, t2_us=math.inf, readout=(0.0, 0.0))
    noise = model_from_calibration(calibration([perfect], [sx(0, 0.0, r)])).qubits[0]
    p = 2 * r
    flip = Circuit(1).sx(0).sx(0).measure(0, 0)
    assert predict_tails(noise, flip) == pytest.approx((1 + (1 - p) ** 2) / 2, abs=EXACT)
