import json
import os
import secrets
import shutil
from collections.abc import Callable, Sequence
from dataclasses import replace
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

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> HardwareJobResult:
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
    assert (code, out.splitlines()[0] in {"HEADS", "TAILS"}) == (0, True)
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
    with pytest.raises(ValueError, match="worth a harvest"):
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


def test_the_pool_table_lines_up(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pool = Pool(tmp_path)
    pool.add([1] * 40_000, {"qubit": 104}, label="dbk2ldpffo6c73ban1n0")
    pool.add([0] * 5, {"qubit": 7}, label="x")
    code, out, _ = cli_run(["pool", "--pool", str(tmp_path)], capsys)
    lines = out.splitlines()
    assert code == 0
    # The last column is right-aligned, so aligned columns mean equal-length lines.
    assert len({len(line) for line in lines}) == 1, lines


@pytest.mark.parametrize("shots", [4096, 10_000])
@pytest.mark.parametrize("p_tails", [0.5, 0.53])
def test_a_harvest_the_forecast_allows_does_extract(
    calibration: dict[str, Any], shots: int, p_tails: float
) -> None:
    # Before 0077, 1,000 shots passed the forecast and then extracted nothing.
    chosen = harvest.plan("b", calibration, shots)
    assert chosen.expected_bits >= harvest.MIN_HARVEST_BITS
    for seed in range(5):
        x = (np.random.default_rng(100 + seed).random(shots) < p_tails).astype(np.uint8)
        assert secure_length(shots, SAFETY * min_entropy(x)) >= 1


@pytest.mark.parametrize("shots", [130, 1000, 2000])
def test_the_forecast_refuses_harvests_too_small_to_be_worth_it(
    calibration: dict[str, Any], tmp_path: Path, shots: int
) -> None:
    transport = FakeTransport(calibration)
    chosen = harvest.plan("b", calibration, shots)
    assert chosen.expected_bits < harvest.MIN_HARVEST_BITS
    with pytest.raises(ValueError, match="worth a harvest"):
        harvest.harvest(transport, chosen, tmp_path / "runs", Pool(tmp_path / "p"), "x")
    assert transport.runs == []


def test_from_run_does_not_claim_to_archive(
    calibration: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chosen = harvest.plan("b", calibration, SHOTS)
    run_dir = harvest.submit(FakeTransport(calibration), chosen.submission, tmp_path / "runs")
    code, out, _ = cli_run(["harvest", "--from-run", str(run_dir)], capsys)
    assert code == 0
    assert not out.startswith("archived")
    assert out.startswith(f"run          {run_dir}")


def test_an_unreadable_archived_run_still_gets_the_recovery_message(
    calibration: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from coin.archive import ArchiveError  # noqa: PLC0415 - only this test raises it

    def unreadable(_path: Path) -> None:
        raise ArchiveError("meta.json: malformed JSON")

    monkeypatch.setattr(harvest, "load_run", unreadable)
    chosen = harvest.plan("b", calibration, SHOTS)
    with pytest.raises(harvest.HarvestError, match="--from-run"):
        harvest.harvest(
            FakeTransport(calibration), chosen, tmp_path / "runs", Pool(tmp_path / "p"), "x"
        )


def test_a_copied_run_directory_is_still_one_job(
    calibration: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chosen = harvest.plan("b", calibration, SHOTS)
    run_dir = harvest.submit(FakeTransport(calibration), chosen.submission, tmp_path / "runs")
    copy = tmp_path / "elsewhere" / "copy-run"
    shutil.copytree(run_dir, copy)
    assert cli_run(["harvest", "--from-run", str(run_dir)], capsys)[0] == 0
    code, _, err = cli_run(["harvest", "--from-run", str(copy)], capsys)
    assert code == 1
    assert "already pooled" in err


@pytest.mark.parametrize(
    "run", ["2026-11-02-dbjuh5d6p51s73cljo60", "2026-11-01-dbjsk29ffo6c73baaosg"]
)
def test_only_a_harvest_run_can_be_pooled(run: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a harvest run"):
        harvest.extract_run(ROOT / "data" / "runs" / run, Pool(tmp_path))


def test_a_published_harvest_cannot_be_pooled_again(tmp_path: Path) -> None:
    # Chapter 3's harvest: its shots and seed are in git, so its bits are anyone's to compute.
    published = ROOT / "data/runs/2026-11-02-dbk2ldpffo6c73ban1n0"
    with pytest.raises(ValueError, match="already published"):
        harvest.extract_run(published, Pool(tmp_path))


def test_publish_waits_for_the_batch_to_be_spent_then_lets_anyone_recompute_it(
    calibration: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chosen = harvest.plan("b", calibration, SHOTS)
    pool = Pool(tmp_path / "pool")
    result = harvest.harvest(FakeTransport(calibration), chosen, tmp_path / "runs", pool, "x")
    code, _, err = cli_run(["publish", str(result.run_dir), "--pool", str(pool.path)], capsys)
    assert code == 1
    assert "unspent" in err
    assert not (result.run_dir / "extraction.json").exists()

    (draw,) = pool.take(len(result.extraction.bits))
    code, _, err = cli_run(["publish", str(result.run_dir), "--pool", str(pool.path)], capsys)
    assert code == 0, err
    record = json.loads((result.run_dir / "extraction.json").read_text())
    seed = np.unpackbits(np.frombuffer(bytes.fromhex(record["seed"]), dtype=np.uint8))
    shots = harvest.shots_of(load_run(result.run_dir))
    assert np.array_equal(toeplitz(shots, seed[: record["seed_bits"]], record["bits"]), draw.bits)
    assert record["spent_before_publishing"] is True

    code, _, err = cli_run(["publish", str(result.run_dir), "--pool", str(pool.path)], capsys)
    assert code == 1
    assert "already published" in err


def test_publish_refuses_a_copy_of_the_run(calibration: dict[str, Any], tmp_path: Path) -> None:
    chosen = harvest.plan("b", calibration, SHOTS)
    pool = Pool(tmp_path / "pool")
    result = harvest.harvest(FakeTransport(calibration), chosen, tmp_path / "runs", pool, "x")
    pool.take(len(result.extraction.bits))
    copy = tmp_path / "copy-of-run"
    shutil.copytree(result.run_dir, copy)
    with pytest.raises(ValueError, match="came from run"):
        harvest.publish(copy, pool)
    assert not (copy / "extraction.json").exists()


COMMITTED = "data/runs/2026-11-02-dbjuh5d6p51s73cljo60"


@pytest.mark.parametrize("how", ["absolute", "relative", "symlink"])
def test_a_run_tracked_by_git_is_not_pooled(
    how: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The first chip map is committed; any committed run's shots are public, however the
    # path to it is written. A relative path once slipped through.
    path = ROOT / COMMITTED
    if how == "relative":
        monkeypatch.chdir(ROOT)
        path = Path(COMMITTED)
    elif how == "symlink":
        path = tmp_path / "link"
        path.symlink_to(ROOT / COMMITTED)
    code, _, err = cli_run(
        ["harvest", "--from-run", str(path), "--pool", str(tmp_path / "pool")], capsys
    )
    assert code == 1
    assert "tracked by git" in err
    assert not (tmp_path / "pool").exists()


def test_a_run_git_cannot_vouch_for_is_not_pooled(
    calibration: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A repository git cannot read: whether the run is committed is unknown, so it is refused.
    (tmp_path / ".git").write_text("gitdir: /nonexistent\n")
    chosen = harvest.plan("b", calibration, SHOTS)
    run_dir = harvest.submit(FakeTransport(calibration), chosen.submission, tmp_path / "runs")
    code, _, err = cli_run(
        ["harvest", "--from-run", str(run_dir), "--pool", str(tmp_path / "pool")], capsys
    )
    assert code == 1
    assert "git could not say whether it is tracked" in err
    assert not (tmp_path / "pool").exists()


def test_a_run_with_no_prediction_is_named_as_such(
    calibration: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chosen = harvest.plan("b", calibration, SHOTS)
    run_dir = harvest.submit(FakeTransport(calibration), chosen.submission, tmp_path / "runs")
    real = harvest.load_run
    monkeypatch.setattr(harvest, "load_run", lambda d: replace(real(d), prediction=None))
    with pytest.raises(ValueError, match="has no prediction"):
        harvest.extract_run(run_dir, Pool(tmp_path / "p"))


def test_git_tracking_is_judged_by_the_runs_own_repository(
    calibration: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Inside a git hook GIT_DIR points at this repository; a run outside it is still untracked.
    monkeypatch.setenv("GIT_DIR", str(ROOT / ".git"))
    chosen = harvest.plan("b", calibration, SHOTS)
    run_dir = harvest.submit(FakeTransport(calibration), chosen.submission, tmp_path / "runs")
    code, _, err = cli_run(["harvest", "--from-run", str(run_dir)], capsys)
    assert code == 0, err


def test_a_harvest_seeds_its_extraction_from_the_operating_system(
    calibration: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A constant seed would make every batch's bits a fixed function of public shots.
    monkeypatch.setattr(secrets, "token_bytes", lambda n: b"\xff" * n)
    chosen = harvest.plan("b", calibration, SHOTS)
    pool = Pool(tmp_path / "pool")
    harvest.harvest(FakeTransport(calibration), chosen, tmp_path / "runs", pool, "x")
    (batch,) = pool.status()
    packed = np.frombuffer(bytes.fromhex(batch.provenance["seed"]), dtype=np.uint8)
    assert np.unpackbits(packed)[: batch.provenance["seed_bits"]].all()
