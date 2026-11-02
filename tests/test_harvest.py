import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from coin import cli, harvest
from coin.archive import load_run
from coin.extract import SAFETY, min_entropy, secure_length, toeplitz
from coin.hardware import JobResult as HardwareJobResult
from coin.noise import model_from_calibration
from coin.pool import Pool

ROOT = Path(__file__).resolve().parent.parent
FIRST_RUN = ROOT / "data/runs/2026-11-01-dbjsk29ffo6c73baaosg"
SHOTS = 20_000


@pytest.fixture(scope="module")
def calibration() -> dict[str, Any]:
    return load_run(FIRST_RUN).calibration


class FakeTransport:
    """Serves a real calibration and flips one qubit at a fixed rate, with no network."""

    def __init__(self, calibration: dict[str, Any], p_tails: float = 0.6) -> None:
        self._calibration = calibration
        self._p = p_tails
        self.runs: list[tuple[str, tuple[int, ...], int]] = []

    def calibration(self, backend: str) -> dict[str, Any]:
        return self._calibration

    def run(self, backend: str, qasm: str, layout: Sequence[int], shots: int) -> HardwareJobResult:
        self.runs.append((backend, tuple(layout), shots))
        bits = np.random.default_rng(1).random(shots) < self._p
        now = datetime.now(UTC)
        return HardwareJobResult(
            job_id="fakeharvest01",
            submitted_at=now,
            finished_at=now + timedelta(seconds=10),
            memory=tuple("1" if b else "0" for b in bits),
            quantum_seconds=None,
            usage={"qpu_charge_time_seconds": 7},
            executed_ops={"rz": 2, "sx": 1, "measure": 1},
            options={},
        )


def test_the_qubit_is_the_one_whose_readout_errs_least(calibration: dict[str, Any]) -> None:
    model = model_from_calibration(calibration)
    q = harvest.pick_qubit(model)
    err = {k: v.readout.p1_given_0 + v.readout.p0_given_1 for k, v in model.qubits.items()}
    assert err[q] == min(err.values())


def test_the_plan_predicts_before_anything_runs(calibration: dict[str, Any]) -> None:
    chosen = harvest.plan("ibm_marrakesh", calibration, SHOTS)
    values = chosen.submission.prediction.values
    assert (values["purpose"], values["qubit"], values["shots"]) == ("harvest", chosen.qubit, SHOTS)
    assert chosen.submission.layout == (chosen.qubit,)
    assert 0.4 < values["p_tails"] < 0.6
    assert chosen.submission.prediction.written_at <= datetime.now(UTC)


def test_a_harvest_archives_the_raw_run_and_pools_extracted_bits(
    calibration: dict[str, Any], tmp_path: Path
) -> None:
    transport = FakeTransport(calibration)
    chosen = harvest.plan("ibm_marrakesh", calibration, SHOTS)
    pool = Pool(tmp_path / "pool")
    result = harvest.harvest(
        transport, chosen, tmp_path / "runs", pool, submit_script="coin harvest"
    )

    # The raw shots are an archived run like any other, prediction and memory included.
    run = load_run(result.run_dir)
    assert run.qubits == (chosen.qubit,)
    assert run.memory is not None
    assert len(run.memory) == SHOTS
    assert run.prediction is not None
    assert run.prediction.written_at < run.submitted_at
    shots = harvest.shots_of(run)

    # The batch is as long as half the estimate allows, and its provenance names the run.
    (batch,) = pool.status()
    expected = secure_length(SHOTS, SAFETY * min_entropy(shots))
    assert batch.total == expected == len(result.extraction.bits)
    assert (batch.provenance["run"], batch.provenance["qubit"]) == (
        result.run_dir.name,
        chosen.qubit,
    )

    # And it is enough to redo the extraction from the archive: same seed, same bits.
    seed = np.unpackbits(np.frombuffer(bytes.fromhex(batch.provenance["seed"]), dtype=np.uint8))
    seed = seed[: batch.provenance["seed_bits"]]
    (draw,) = pool.take(batch.total)
    assert np.array_equal(toeplitz(shots, seed, batch.total), draw.bits)


def cli_run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    try:
        code = cli.main(argv)
    except SystemExit as exit_info:
        code = int(exit_info.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def test_a_dry_run_submits_nothing(
    calibration: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transport = FakeTransport(calibration)
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    code, out, _ = cli_run(["harvest", "--backend", "b", "--shots", "100000", "--dry-run"], capsys)
    assert code == 0
    assert "dry run: nothing submitted" in out
    assert "~27 QPU seconds" in out
    assert transport.runs == []
    assert Pool().status() == []


def test_harvest_then_flip_then_run_dry(
    calibration: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cli, "_transport", lambda: FakeTransport(calibration))
    argv = ["harvest", "--backend", "b", "--shots", str(SHOTS), "--submit"]
    code, out, err = cli_run([*argv, "--runs-dir", str(tmp_path / "runs")], capsys)
    assert code == 0, err
    assert "pooled       batch" in out
    (batch,) = Pool().status()

    code, out, _ = cli_run(["flip"], capsys)
    assert (code, out.strip() in {"HEADS", "TAILS"}) == (0, True)
    code, out, _ = cli_run(["pool"], capsys)
    assert f"{batch.total - 1:>10,}" in out

    code, out, _ = cli_run(["flip", "--shots", str(batch.total - 1)], capsys)
    assert code == 0
    code, out, err = cli_run(["flip"], capsys)
    assert code == 1
    assert "run `coin harvest`" in err


def test_an_empty_pool_exits_non_zero_and_says_to_harvest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out, err = cli_run(["flip"], capsys)
    assert (code, out) == (1, "")
    assert "run `coin harvest`" in err
    code, out, _ = cli_run(["pool"], capsys)
    assert code == 0
    assert "run `coin harvest`" in out


def test_seed_without_sim_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli_run(["flip", "--seed", "1"], capsys)
    assert code == 2
    assert "needs --sim" in err


def test_tests_never_touch_the_users_pool() -> None:
    assert "pool" in Path(os.environ["COIN_POOL"]).name
    assert not str(Pool().path).startswith(str(Path.home() / ".local"))


def test_a_harvest_too_small_to_yield_a_bit_is_refused_before_it_runs(
    calibration: dict[str, Any], tmp_path: Path
) -> None:
    transport = FakeTransport(calibration)
    chosen = harvest.plan("b", calibration, 100)  # 100 · ½ · ~1 bit − 64 < 1
    with pytest.raises(ValueError, match="no bits"):
        harvest.harvest(transport, chosen, tmp_path / "runs", Pool(tmp_path / "pool"), "x")
    assert transport.runs == []


def test_an_unwritable_pool_is_refused_before_it_runs(
    calibration: dict[str, Any], tmp_path: Path
) -> None:
    transport = FakeTransport(calibration)
    blocked = tmp_path / "file"
    blocked.write_text("a file where the pool directory should be")
    chosen = harvest.plan("b", calibration, SHOTS)
    with pytest.raises((FileExistsError, NotADirectoryError)):
        harvest.harvest(transport, chosen, tmp_path / "runs", Pool(blocked / "pool"), "x")
    assert transport.runs == []


def test_a_failed_extraction_keeps_the_run_and_can_be_retried(
    calibration: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport(calibration)
    chosen = harvest.plan("b", calibration, SHOTS)
    pool = Pool(tmp_path / "pool")

    def broken(*args: object, **kwargs: object) -> None:
        raise ValueError("simulated failure")

    monkeypatch.setattr(harvest, "toeplitz_extract", broken)
    with pytest.raises(harvest.HarvestError, match="--from-run") as caught:
        harvest.harvest(transport, chosen, tmp_path / "runs", pool, "x")
    assert pool.status() == []
    (run_dir,) = (tmp_path / "runs").iterdir()
    assert str(run_dir) in str(caught.value)

    monkeypatch.undo()
    result = harvest.extract_run(run_dir, pool)
    assert pool.status()[0].total == len(result.extraction.bits) > 0
    assert len(transport.runs) == 1


def test_from_run_on_the_command_line(
    calibration: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chosen = harvest.plan("b", calibration, SHOTS)
    run_dir = harvest.submit(FakeTransport(calibration), chosen.submission, tmp_path / "runs")
    code, out, err = cli_run(["harvest", "--from-run", str(run_dir)], capsys)
    assert code == 0, err
    assert "pooled       batch" in out
    assert Pool().status()[0].provenance["run"] == run_dir.name


def test_the_archived_command_names_where_it_wrote(
    calibration: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cli, "_transport", lambda: FakeTransport(calibration))
    runs, pool = tmp_path / "runs", tmp_path / "pool"
    argv = ["harvest", "--backend", "b", "--shots", str(SHOTS), "--submit"]
    code, _, err = cli_run([*argv, "--runs-dir", str(runs), "--pool", str(pool)], capsys)
    assert code == 0, err
    (run_dir,) = runs.iterdir()
    script = load_run(run_dir).submit_script
    assert script is not None
    assert f"--runs-dir {runs}" in script
    assert f"--pool {pool}" in script


def test_harvest_without_a_mode_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli_run(["harvest", "--backend", "b"], capsys)
    assert code == 2
    assert "--from-run" in err


def test_a_corrupt_pool_is_reported_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pool = Pool(tmp_path)
    pool.add([1, 0], {}, label="a")
    (tmp_path / "spent.json").write_text("{not json")
    code, _, err = cli_run(["flip", "--pool", str(tmp_path)], capsys)
    assert code == 1
    assert "could not be read" in err


def test_a_run_already_pooled_is_refused(
    calibration: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chosen = harvest.plan("b", calibration, SHOTS)
    run_dir = harvest.submit(FakeTransport(calibration), chosen.submission, tmp_path / "runs")
    assert cli_run(["harvest", "--from-run", str(run_dir)], capsys)[0] == 0
    code, _, err = cli_run(["harvest", "--from-run", str(run_dir)], capsys)
    assert code == 1
    assert "already pooled" in err


def test_coin_pool_reports_a_corrupt_pool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    Pool(tmp_path).add([1, 0], {}, label="a")
    (tmp_path / "spent.json").write_text("{not json")
    code, _, err = cli_run(["pool", "--pool", str(tmp_path)], capsys)
    assert code == 1
    assert "could not be read" in err


def test_pool_with_sim_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli_run(["flip", "--sim", "--pool", str(tmp_path)], capsys)
    assert code == 2
    assert "--sim" in err
