from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from coin import cli, readout
from coin.archive import load_run
from coin.hardware import JobResult, submit
from coin.noise import model_from_calibration

ROOT = Path(__file__).resolve().parent.parent
FIRST_RUN = ROOT / "data/runs/2026-11-01-dbjsk29ffo6c73baaosg"


@pytest.fixture(scope="module")
def calibration() -> dict[str, Any]:
    return load_run(FIRST_RUN).calibration


class FakeTransport:
    """Reads each qubit as 1 with exactly its published probability, so 3σ mostly holds."""

    def __init__(self, calibration: dict[str, Any], prepare: int) -> None:
        self._calibration = calibration
        n = len(calibration["qubits"])
        self._p = np.full(n, 0.5)
        published, _ = readout.published_readout(calibration, prepare)
        for q, error in published.items():
            self._p[q] = error if prepare == 0 else 1 - error
        self.runs: list[int] = []

    def calibration(self, backend: str) -> dict[str, Any]:
        return self._calibration

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
        *,
        parameter_values: Sequence[Sequence[float]] | None = None,
    ) -> JobResult:
        self.runs.append(shots)
        bits = np.random.default_rng(2).random((shots, len(layout))) < self._p
        now = datetime.now(UTC)
        return JobResult(
            job_id="fakereadout01",
            submitted_at=now,
            finished_at=now + timedelta(seconds=10),
            memory=tuple("".join("1" if b else "0" for b in row[::-1]) for row in bits),
            quantum_seconds=None,
            usage={"qpu_charge_time_seconds": 7},
            executed_ops={"measure": len(layout)},
            options={},
        )


@pytest.mark.parametrize("prepare", [0, 1])
def test_the_plan_prepares_every_qubit_and_predicts_its_published_error(
    calibration: dict[str, Any], prepare: int
) -> None:
    chosen = readout.plan("b", calibration, 1000, prepare)
    n = len(calibration["qubits"])
    names = [getattr(op, "name", "measure") for op in chosen.submission.circuit.ops]
    assert names.count("x") == (n if prepare else 0)
    assert names.count("measure") == n
    field = "prob_meas1_prep0" if prepare == 0 else "prob_meas0_prep1"
    raw = {f["name"]: f["value"] for f in calibration["qubits"][0]}
    expected = raw[field] if prepare == 0 else 1 - raw[field]
    assert chosen.submission.prediction.values["p_read_1"]["0"] == pytest.approx(
        expected, abs=1e-12
    )


def test_qubits_the_model_excludes_are_still_tested(calibration: dict[str, Any]) -> None:
    # The model drops qubits for T1/T2 or gate faults, and for readout too bad to model;
    # their published readout is exactly what this run should test.
    model = model_from_calibration(calibration)
    chosen = readout.plan("b", calibration, 1000, 0)
    with_readout = set(model.excluded) - set(chosen.unpublished)
    assert with_readout
    assert with_readout <= set(chosen.published)


def test_a_malformed_calibration_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="not a calibration snapshot"):
        readout.plan("b", {"gates": []}, 10, 0)


def test_the_summary_survives_a_calibration_with_no_readout(calibration: dict[str, Any]) -> None:
    stripped = {**calibration, "qubits": [[{"name": "T1", "value": 1.0}] for _ in range(3)]}
    text = readout.summary(readout.plan("b", stripped, 10, 0))
    assert "no qubit publishes a readout error" in text
    assert "unpublished  3" in text


def test_measured_pairs_the_two_runs_per_qubit(calibration: dict[str, Any], tmp_path: Path) -> None:
    runs = {}
    for prepare in (0, 1):
        chosen = readout.plan("b", calibration, 20_000, prepare)
        runs[prepare] = load_run(
            submit(FakeTransport(calibration, prepare), chosen.submission, tmp_path / str(prepare))
        )
    got = readout.measured(runs[0], runs[1])
    model = model_from_calibration(calibration)
    q = min(model.qubits)
    # The fake reads at the published rates; 20,000 shots pin each to about ±0.1%.
    assert got[q].p1_given_0 == pytest.approx(model.qubits[q].readout.p1_given_0, abs=0.005)
    assert got[q].p0_given_1 == pytest.approx(model.qubits[q].readout.p0_given_1, abs=0.005)
    with pytest.raises(ValueError, match=r"not a prepare-\|0⟩ readout run"):
        readout.measured(runs[1], runs[0])


@pytest.mark.parametrize("prepare", [0, 1])
def test_a_readout_run_is_archived_and_scored_against_the_prediction(
    calibration: dict[str, Any], tmp_path: Path, prepare: int
) -> None:
    chosen = readout.plan("b", calibration, 20_000, prepare)
    run = load_run(submit(FakeTransport(calibration, prepare), chosen.submission, tmp_path))
    hits, total = readout.within_three_sigma(run)
    # The fake reads exactly at the published rates: about 99.7% land within 3σ.
    assert total == len(chosen.published)
    assert hits >= total - 3


def test_a_wrong_prediction_is_scored_as_wrong(calibration: dict[str, Any], tmp_path: Path) -> None:
    # Prepared |0⟩ but read as if |1⟩ had been prepared: nearly every qubit misses.
    chosen = readout.plan("b", calibration, 20_000, 0)
    run = load_run(submit(FakeTransport(calibration, 1), chosen.submission, tmp_path))
    hits, total = readout.within_three_sigma(run)
    assert hits < total // 10


def test_only_readout_runs_are_scored() -> None:
    with pytest.raises(ValueError, match="not a readout run"):
        readout.within_three_sigma(load_run(FIRST_RUN))


@pytest.mark.parametrize(
    ("shots", "prepare", "message"), [(0, 0, "shots"), (10, 2, "prepare 0 or 1")]
)
def test_impossible_plans_are_refused(
    calibration: dict[str, Any], shots: int, prepare: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        readout.plan("b", calibration, shots, prepare)


def cli_run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    try:
        code = cli.main(argv)
    except SystemExit as exit_info:
        code = int(exit_info.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def test_the_dry_run_submits_nothing(
    calibration: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transport = FakeTransport(calibration, 1)
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    argv = ["run", "readout", "--backend", "b", "--shots", "20000", "--prepare", "1", "--dry-run"]
    code, out, _ = cli_run(argv, capsys)
    assert code == 0
    assert "prepare |1⟩" in out
    assert "~7 QPU seconds" in out
    assert transport.runs == []


def test_submitting_archives_and_reports(
    calibration: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cli, "_transport", lambda: FakeTransport(calibration, 0))
    argv = ["run", "readout", "--backend", "b", "--shots", "20000", "--prepare", "0", "--submit"]
    code, out, err = cli_run([*argv, "--runs-dir", str(tmp_path)], capsys)
    assert code == 0, err
    assert "read within 3σ of their published error" in out  # noqa: RUF001 - σ is the display text
    (run_dir,) = tmp_path.iterdir()
    assert load_run(run_dir).prediction is not None


def test_measured_uses_each_runs_own_shot_count(
    calibration: dict[str, Any], tmp_path: Path
) -> None:
    # The two calibration jobs need not have the same number of shots.
    runs = {}
    for prepare, shots in ((0, 20_000), (1, 8_000)):
        chosen = readout.plan("b", calibration, shots, prepare)
        runs[prepare] = load_run(
            submit(FakeTransport(calibration, prepare), chosen.submission, tmp_path / str(prepare))
        )
    got = readout.measured(runs[0], runs[1])
    q = min(got)
    ones_0 = sum(c for o, c in runs[0].counts.items() if o[len(o) - 1 - q] == "1")
    ones_1 = sum(c for o, c in runs[1].counts.items() if o[len(o) - 1 - q] == "1")
    assert got[q].p1_given_0 == pytest.approx(ones_0 / 20_000, abs=1e-12)
    assert got[q].p0_given_1 == pytest.approx(1 - ones_1 / 8_000, abs=1e-12)


def test_a_readout_published_as_worse_than_a_coin_is_still_tested() -> None:
    # Qubit 119 published p(0|1) = 0.54 in the first chip map's calibration: exactly the kind
    # of readout this run exists to check, not one to drop.
    calibration = load_run(ROOT / "data/runs/2026-11-02-dbjuh5d6p51s73cljo60").calibration
    chosen = readout.plan("b", calibration, 1000, 1)
    assert 119 in chosen.published
    assert chosen.published[119] == pytest.approx(0.5400390625, abs=1e-12)
