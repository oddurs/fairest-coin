import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from coin import cli
from coin.archive import Prediction, Run, load_run
from coin.chipmap import MAX_SHOTS, estimate_qpu_seconds, plan, summary, tails_by_qubit
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
