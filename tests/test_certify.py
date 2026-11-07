"""The coin's own bits choose the settings; a violation certifies bits back, at a loss."""

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from coin import bell, certify, chsh, cli
from coin.archive import EXTRACTION, load_run
from coin.hardware import submit
from coin.pool import Pool
from tests.test_chsh import CALIBRATION
from tests.test_commitment import MEASURED, git, readout_runs, repo  # noqa: F401 - repo is a fixture
from tests.test_harvest import cli_run
from tests.test_sweep import SweepTransport


@pytest.mark.parametrize(
    ("s", "rate"),
    [(1.5, 0.0), (2.0, 0.0), (2.5, 0.268), (2.7, 0.493), (2 * math.sqrt(2), 1.0), (3.0, 1.0)],
)
def test_the_certified_rate_is_pironios_bound(s: float, rate: float) -> None:
    assert certify.certified_rate(s) == pytest.approx(rate, abs=1e-3)


def test_the_certified_rate_rises_with_s() -> None:
    rates = [certify.certified_rate(s) for s in np.linspace(2.0, 2 * math.sqrt(2), 50)]
    assert rates == sorted(rates)


def test_settings_come_two_pool_bits_a_round(tmp_path: Path) -> None:
    pool = Pool(tmp_path / "pool")
    pool.add([0, 0, 0, 1, 1, 0], {}, label="a")
    pool.add([1, 1, 0, 1], {}, label="b")
    choices, sources = certify.settings_from_pool(pool, 5)
    # Pairs (0,0), (0,1), (1,0), (1,1), (0,1): choice 2a + b.
    assert choices == (0, 1, 2, 3, 1)
    assert [(s["offset"], s["bits"]) for s in sources] == [(0, 6), (0, 4)]
    assert sum(b.remaining for b in pool.status()) == 0


def chsh_run(
    tmp_path: Path, transport: Any, rounds: int, *, from_pool: bool = True
) -> tuple[Path, Pool]:
    """A CHSH run archived from a plan whose settings came from a pool (or not)."""
    pool = Pool(tmp_path / "pool")
    pool.add(np.random.default_rng(9).integers(0, 2, 2 * rounds), {}, label="settings")
    choices, sources = certify.settings_from_pool(pool, rounds)
    chosen = bell.plan_chsh("fake", CALIBRATION, choices, measured=MEASURED)
    values = dict(chosen.submission.prediction.values)
    if from_pool:
        values["settings_source"] = {"pool": sources}
    submission = replace(
        chosen.submission, prediction=replace(chosen.submission.prediction, values=values)
    )
    return submit(transport, submission, tmp_path / "runs"), pool


@pytest.fixture(autouse=True)
def fewer_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chsh, "INTERVAL_DRAWS", 20)


def test_a_violation_is_hashed_at_the_certified_rate_and_pooled(tmp_path: Path) -> None:
    run_dir, pool = chsh_run(tmp_path, SweepTransport(np.random.default_rng(10)), 4000)
    result = certify.certify(run_dir, pool)
    assert result.s_low > 2
    assert result.rate_per_round == pytest.approx(certify.certified_rate(result.s_low))
    assert result.extraction is not None
    # Two outcome bits a round at rate/2 each: ⌊n·rate⌋ − 64 bits out.
    assert result.certified_bits == math.floor(4000 * result.rate_per_round) - 64
    assert result.setting_bits == 8000
    assert result.net == result.certified_bits - 8000 < 0
    (batch,) = [b for b in pool.status() if b.batch == result.batch]
    assert batch.provenance["certified"] is True
    assert batch.provenance["s_low"] == result.s_low
    assert batch.provenance["settings_source"]["pool"][0]["bits"] == 8000
    text = certify.report(result)
    assert "does not expand it" in text
    assert f"{result.net:+,}" in text


def test_a_run_whose_s_low_does_not_exceed_2_credits_nothing(tmp_path: Path) -> None:
    class Local(SweepTransport):
        # Both sides always answer 0: the best local strategy, S = 2 exactly.
        def run(self, *args: Any, **kwargs: Any) -> Any:
            result = super().run(*args, **kwargs)
            return replace(result, memory=("00",) * len(result.memory))

    run_dir, pool = chsh_run(tmp_path, Local(np.random.default_rng(11)), 4000)
    before = [b.batch for b in pool.status()]
    result = certify.certify(run_dir, pool)
    assert result.s_low < 2
    assert result.certified_bits == 0
    assert result.batch is None
    assert [b.batch for b in pool.status()] == before
    assert "nothing credited" in certify.report(result)


def test_a_run_whose_settings_did_not_come_from_the_pool_is_refused(tmp_path: Path) -> None:
    run_dir, pool = chsh_run(
        tmp_path, SweepTransport(np.random.default_rng(12)), 400, from_pool=False
    )
    with pytest.raises(ValueError, match="did not come from the pool"):
        certify.certify(run_dir, pool)


def test_a_run_is_certified_once_and_never_once_published(tmp_path: Path) -> None:
    run_dir, pool = chsh_run(tmp_path, SweepTransport(np.random.default_rng(13)), 4000)
    certify.certify(run_dir, pool)
    with pytest.raises(ValueError, match="already pooled"):
        certify.certify(run_dir, pool)
    (run_dir / EXTRACTION).write_text("{}")
    with pytest.raises(ValueError, match="already published"):
        certify.certify(run_dir, pool)


def test_predict_draws_the_settings_from_the_pool(
    repo: Path,  # noqa: F811 - the fixture
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runs = repo / "runs"
    zero, one = readout_runs(runs)
    pool = Pool(repo / "pool")
    pool.add(np.random.default_rng(14).integers(0, 2, 5000), {}, label="harvest")
    monkeypatch.setattr(cli, "_transport", lambda: SweepTransport(np.random.default_rng(15)))
    base = ["run", "chsh", "--backend", "fake", "--rounds", "2000", "--pool", str(repo / "pool")]
    readout = ["--readout", str(zero), str(one)]
    code, out, _ = cli_run([*base, *readout, "--dry-run"], capsys)
    assert code == 0
    assert "no pool bit spent" in out
    assert pool.status()[0].spent == 0
    predictions = repo / "predictions"
    code, out, err = cli_run(
        [*base, *readout, "--predict", "--predictions-dir", str(predictions)], capsys
    )
    assert code == 0, err
    assert "4,000 pool bits spent" in out
    assert pool.status()[0].spent == 4000
    (path,) = predictions.iterdir()
    plan = bell.load_prediction(path)
    # What was printed is the prediction, not the throwaway plan that validated it.
    assert plan.interval is not None
    assert f"[{plan.interval[0]:.3f}, {plan.interval[1]:.3f}]" in out
    sources = plan.submission.prediction.values["settings_source"]
    assert sources == {"pool": [{"batch": pool.status()[0].batch, "offset": 0, "bits": 4000}]}


def test_coin_certify_refuses_a_committed_run(
    repo: Path,  # noqa: F811 - the fixture
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir, _ = chsh_run(repo, SweepTransport(np.random.default_rng(16)), 400)
    git(repo, "add", "runs")
    git(repo, "commit", "--quiet", "-m", "publish the run")
    code, _, err = cli_run(["certify", str(run_dir), "--pool", str(repo / "pool")], capsys)
    assert code == 1
    assert "tracked by git" in err


def test_coin_certify_reports_the_net(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_dir, _ = chsh_run(tmp_path, SweepTransport(np.random.default_rng(17)), 4000)
    code, out, err = cli_run(["certify", str(run_dir), "--pool", str(tmp_path / "pool")], capsys)
    assert code == 0, err
    assert "certified bits in batch" in out
    assert "net          -" in out
    assert load_run(run_dir).job_id in out


def test_the_pool_table_names_a_certified_batchs_pair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir, pool = chsh_run(tmp_path, SweepTransport(np.random.default_rng(18)), 4000)
    certify.certify(run_dir, pool)
    code, out, _ = cli_run(["pool", "--pool", str(tmp_path / "pool")], capsys)
    assert code == 0
    assert " 2-3 " in out


@pytest.mark.parametrize(("rounds", "seconds"), [(2_000, 4), (12_000, 6), (22_000, 9)])
def test_the_estimate_fits_what_swept_jobs_were_charged(rounds: int, seconds: int) -> None:
    chosen = bell.plan_chsh("fake", CALIBRATION, (0, 1, 2, 3) * (rounds // 4))
    assert f"~{seconds} QPU seconds" in bell.chsh_summary(chosen)
