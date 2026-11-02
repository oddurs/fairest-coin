import json
import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from coin import cli
from coin.archive import Prediction, Run, load_run
from coin.chipmap import (
    MAX_SHOTS,
    _drift,
    compare,
    estimate_qpu_seconds,
    plan,
    report,
    summary,
    tails_by_qubit,
)
from coin.circuit import Gate
from coin.hardware import JobResult
from coin.ibm import MissingCredentialsError

ROOT = Path(__file__).resolve().parent.parent
FIRST_RUN = ROOT / "data/runs/2026-11-01-dbjsk29ffo6c73baaosg"
EXACT = 1e-12


@pytest.fixture(scope="module")
def calibration() -> dict[str, Any]:
    return load_run(FIRST_RUN).calibration


class FakeTransport:
    """Serves a real calibration and flips each qubit at a fixed rate, with no network."""

    def __init__(self, calibration: dict[str, Any], p_tails: float = 0.5) -> None:
        self._calibration = calibration
        self._p = p_tails
        self.runs: list[tuple[str, int]] = []

    def calibration(self, backend: str) -> dict[str, Any]:
        return self._calibration

    def run(self, backend: str, qasm: str, layout: Sequence[int], shots: int) -> JobResult:
        self.runs.append((backend, shots))
        bits = np.random.default_rng(0).random((shots, len(layout))) < self._p
        memory = tuple("".join("1" if b else "0" for b in row[::-1]) for row in bits)
        now = datetime.now(UTC)
        return JobResult(
            job_id="fakechipmap01",
            submitted_at=now,
            finished_at=now + timedelta(seconds=30),
            memory=memory,
            quantum_seconds=None,
            usage={"qpu_charge_time_seconds": 27},
            executed_ops={"rz": 2 * len(layout), "sx": len(layout), "measure": len(layout)},
            options={},
        )


def test_the_plan_predicts_every_usable_qubit_before_anything_runs(
    calibration: dict[str, Any],
) -> None:
    before = datetime.now(UTC)
    chip = plan("ibm_marrakesh", calibration, 4096)
    assert len(chip.p_tails) == 149
    assert set(chip.excluded) == {20, 82, 83, 94, 113, 119, 130}
    assert chip.submission.prediction.written_at >= before
    values = chip.submission.prediction.values
    assert set(values["p_tails"]) == {str(q) for q in chip.p_tails}
    assert set(values["excluded"]) == {str(q) for q in chip.excluded}


def test_the_alternative_model_predicts_more_heads(calibration: dict[str, Any]) -> None:
    chip = plan("ibm_marrakesh", calibration, 4096)
    shared = chip.p_tails.keys() & chip.p_tails_measurement_decay.keys()
    assert shared
    assert all(chip.p_tails_measurement_decay[q] < chip.p_tails[q] for q in shared)


def test_the_circuit_flips_every_qubit_in_parallel(calibration: dict[str, Any]) -> None:
    submission = plan("ibm_marrakesh", calibration, 10).submission
    assert submission.circuit.n_qubits == 156
    assert submission.layout == tuple(range(156))
    gates = [op for op in submission.circuit.ops if isinstance(op, Gate)]
    assert [g.name for g in gates[:3]] == ["rz", "sx", "rz"]
    assert len(gates) == 3 * 156


@pytest.mark.parametrize("shots", [0, MAX_SHOTS + 1])
def test_shots_beyond_one_job_are_refused(calibration: dict[str, Any], shots: int) -> None:
    with pytest.raises(ValueError, match="shots must be between"):
        plan("ibm_marrakesh", calibration, shots)


def test_the_cost_estimate_reproduces_the_first_run() -> None:
    # Spike 0015: 4,096 shots billed 3 QPU seconds.
    assert estimate_qpu_seconds(4096) == pytest.approx(3.0, abs=0.1)
    assert estimate_qpu_seconds(MAX_SHOTS) == pytest.approx(27.0, abs=EXACT)


def test_tails_are_counted_per_physical_qubit() -> None:
    now = datetime.now(UTC)
    run = Run(
        job_id="j",
        backend="b",
        qubits=(5, 9),
        shots=4,
        submitted_at=now,
        finished_at=now,
        circuit_qasm="",
        counts={"01": 3, "11": 1},  # classical bit 0 (qubit 5) is the rightmost character
        calibration={},
        prediction=Prediction(now - timedelta(seconds=1), {}),
    )
    assert tails_by_qubit(run) == {5: 4, 9: 1}


def test_the_summary_states_cost_and_exclusions(calibration: dict[str, Any]) -> None:
    text = summary(plan("ibm_marrakesh", calibration, MAX_SHOTS))
    assert "156 qubits" in text
    assert "~27 QPU seconds" in text
    assert "excluded     7" in text


def run_cli(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    try:
        code = cli.main(argv)
    except SystemExit as exit_info:
        code = int(exit_info.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def test_a_dry_run_submits_nothing(
    calibration: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = FakeTransport(calibration)
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    code, out, _ = run_cli(
        ["run", "chip-map", "--backend", "ibm_marrakesh", "--shots", "100000", "--dry-run"],
        capsys,
    )
    assert code == 0
    assert "~27 QPU seconds" in out
    assert "dry run: nothing submitted" in out
    assert transport.runs == []


def test_submitting_archives_the_run_with_its_earlier_prediction(
    calibration: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    transport = FakeTransport(calibration)
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    argv = ["run", "chip-map", "--backend", "ibm_marrakesh", "--shots", "2000", "--submit"]
    code, out, _ = run_cli([*argv, "--runs-dir", str(tmp_path)], capsys)
    assert code == 0, out
    assert transport.runs == [("ibm_marrakesh", 2000)]
    (directory,) = tmp_path.iterdir()
    run = load_run(directory)
    assert run.prediction is not None
    assert run.prediction.written_at < run.submitted_at
    assert len(tails_by_qubit(run)) == 156
    meta = json.loads((directory / "meta.json").read_text())
    assert meta["qubits"] == list(range(156))
    assert "qubits within 3" in out


def test_without_credentials_the_command_says_so(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_credentials() -> FakeTransport:
        raise MissingCredentialsError("QISKIT_IBM_TOKEN is not set")

    monkeypatch.setattr(cli, "_transport", no_credentials)
    code, out, err = run_cli(
        ["run", "chip-map", "--backend", "x", "--shots", "10", "--dry-run"], capsys
    )
    assert code == 1
    assert out == ""
    assert "QISKIT_IBM_TOKEN" in err


@pytest.mark.parametrize("flags", [[], ["--dry-run", "--submit"]])
def test_exactly_one_of_dry_run_or_submit_is_required(
    flags: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, _ = run_cli(["run", "chip-map", "--backend", "x", "--shots", "10", *flags], capsys)
    assert code == 2


def test_more_shots_than_one_job_allows_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _, err = run_cli(
        ["run", "chip-map", "--backend", "x", "--shots", "100001", "--dry-run"], capsys
    )
    assert code == 2
    assert "100,000" in err


def chip_map_run(counts: dict[str, int], values: dict[str, Any]) -> Run:
    now = datetime.now(UTC)
    return Run(
        job_id="j",
        backend="b",
        qubits=(5, 9),
        shots=sum(counts.values()),
        submitted_at=now,
        finished_at=now,
        circuit_qasm="",
        counts=counts,
        calibration={},
        prediction=Prediction(now - timedelta(seconds=1), values),
    )


def test_compare_pairs_each_prediction_with_its_qubits_measurement() -> None:
    # Qubit 5 (classical bit 0, rightmost) is tails in 300 of 400 shots, qubit 9 in 100.
    run = chip_map_run(
        {"01": 200, "11": 100, "00": 100},
        {"p_tails": {"9": 0.2, "5": 0.75}, "p_tails_measurement_decay": {"5": 0.7}},
    )
    nine, five = sorted(compare(run), key=lambda r: -r.qubit)
    assert (five.qubit, five.predicted, five.alternative) == (5, 0.75, 0.7)
    assert five.measured == pytest.approx(0.75, abs=EXACT)
    assert five.z == pytest.approx(0.0, abs=EXACT)
    assert (nine.qubit, nine.alternative) == (9, None)
    assert nine.measured == pytest.approx(0.25, abs=EXACT)
    # σ is the prediction's own binomial spread: √(0.2 · 0.8 / 400) = 0.02, so 0.05 is 2.5σ.
    assert nine.sigma == pytest.approx(0.02, abs=EXACT)
    assert nine.z == pytest.approx(2.5, abs=EXACT)


def test_compare_returns_qubits_in_numeric_order() -> None:
    run = chip_map_run({"00": 1}, {"p_tails": {"9": 0.5, "5": 0.5}})
    assert [r.qubit for r in compare(run)] == [5, 9]


def test_compare_refuses_a_run_that_is_not_a_chip_map() -> None:
    run = chip_map_run({"00": 1}, {"expected_tails": 2046.0})
    with pytest.raises(ValueError, match="not a chip map"):
        compare(run)


def test_compare_refuses_a_single_qubit_run_whose_p_tails_is_one_number() -> None:
    with pytest.raises(ValueError, match="not a chip map"):
        compare(load_run(FIRST_RUN))


CHIP_MAP_RUN = ROOT / "data/runs/2026-11-02-dbjuh5d6p51s73cljo60"


def memory_run(tails: np.ndarray) -> Run:
    """A run whose per-shot memory is `tails` (shots × qubits, True for tails)."""
    shots, width = tails.shape
    # Qubit 0 is the rightmost character of each outcome.
    memory = tuple("".join("1" if bit else "0" for bit in row[::-1]) for row in tails)
    return replace(chip_map_run({}, {}), qubits=tuple(range(width)), shots=shots, memory=memory)


def test_drift_is_standard_normal_for_coins_that_hold_still() -> None:
    # 200 independent fair coins: the spread of 200 standard normals is 1 ± 0.05, so ±0.2
    # is a 4σ band; beyond 3σ about 0.5 are expected and 4 would be rare. The seed fixes it.
    z = _drift(memory_run(np.random.default_rng(7).random((2000, 200)) < 0.5))
    assert sorted(z) == list(range(200))
    assert 0.8 < np.std(list(z.values()), ddof=1) < 1.2
    assert sum(abs(v) > 3 for v in z.values()) <= 3


def test_drift_finds_the_coins_that_change_halfway_by_physical_qubit() -> None:
    # A fifth of the coins move from 50% to 60% tails halfway, which is about 4.5σ each.
    rng = np.random.default_rng(7)
    p = np.full((2000, 200), 0.5)
    p[1000:, :40] = 0.6
    z = _drift(memory_run(rng.random((2000, 200)) < p))
    assert sum(abs(z[q]) > 3 for q in range(40)) >= 30
    assert sum(abs(z[q]) > 3 for q in range(40, 200)) <= 3


def test_the_report_quotes_the_archived_chip_map() -> None:
    text = report(load_run(CHIP_MAP_RUN))
    assert "written 2.3 s before submission; 150 qubits predicted, 6 excluded" in text
    assert re.search(r"within 3σ\s+31\s+16", text)  # noqa: RUF001 - σ is the display text
    assert re.search(r"median bias, measured\s+\+0\.45%", text)
    assert "131 of 150 within 3σ if each sx error may be coherent" in text  # noqa: RUF001
    assert "8 of 156 qubits changed by more than 3σ" in text  # noqa: RUF001
    assert "(0.4 expected if they held still)" in text
    misses = text.split("largest misses")[1].splitlines()[1:]
    assert [line.split()[0] for line in misses] == ["59", "29", "48", "34", "118"]


def test_the_report_leaves_out_drift_without_per_shot_memory() -> None:
    run = load_run(CHIP_MAP_RUN)
    text = report(replace(run, memory=None))
    assert "drift" not in text
    assert "largest misses" in text


def test_compare_command_refuses_a_run_that_is_not_a_chip_map(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out, err = run_cli(["compare", str(FIRST_RUN)], capsys)
    assert (code, out) == (1, "")
    assert "not a chip map" in err


def test_compare_command_reports_a_missing_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run_cli(["compare", str(tmp_path / "nope")], capsys)
    assert code == 1
    assert err.startswith("coin compare: ")


def test_the_report_names_predicted_qubits_without_usable_calibration() -> None:
    run = load_run(CHIP_MAP_RUN)
    assert run.prediction is not None
    values = run.prediction.values
    # Qubit 82 has no T2 in this calibration, so nothing could have predicted it.
    forged = Prediction(
        run.prediction.written_at, {**values, "p_tails": {**values["p_tails"], "82": 0.5}}
    )
    with pytest.raises(ValueError, match=r"predicted qubits \[82\] have no usable calibration"):
        report(replace(run, prediction=forged))


def test_a_chip_map_without_alternative_predictions_is_still_reported() -> None:
    # A calibration with no readout lengths: plan() leaves the alternative empty, and the
    # report used to crash on an empty median.
    run = load_run(CHIP_MAP_RUN)
    assert run.prediction is not None
    values = {**run.prediction.values, "p_tails_measurement_decay": {}}
    text = report(replace(run, prediction=Prediction(run.prediction.written_at, values)))
    assert "alternative  not predicted" in text
    assert re.search(r"within 3σ\s+31\s+—", text)  # noqa: RUF001 - σ is the display text


def test_a_one_qubit_chip_map_is_reported() -> None:
    run = load_run(CHIP_MAP_RUN)
    assert run.prediction is not None
    values = run.prediction.values
    one = {
        **values,
        "p_tails": {"10": values["p_tails"]["10"]},
        "p_tails_measurement_decay": {"10": values["p_tails_measurement_decay"]["10"]},
    }
    text = report(replace(run, prediction=Prediction(run.prediction.written_at, one)))
    assert re.search(r"correlation with measured\s+—\s+—", text)
