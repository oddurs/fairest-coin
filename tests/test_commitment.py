"""Predict, commit, then measure: the CHSH prediction must be in git before its run."""

import gzip
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from coin import bell, chsh, cli, readout
from coin.archive import load_run
from coin.commitment import committed
from coin.hardware import JobResult, submit
from coin.pool import Pool
from coin.readout import ReadoutCounts
from tests.test_chsh import CALIBRATION
from tests.test_hardware import FakeTransport
from tests.test_harvest import cli_run
from tests.test_sweep import SweepTransport


@pytest.fixture(autouse=True)
def fewer_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    # These tests check what the interval is for, not its precision.
    monkeypatch.setattr(chsh, "INTERVAL_DRAWS", 40)


def git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env |= {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    base = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    done = subprocess.run(
        [*base, *args], cwd=repo, env=env, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "--quiet")
    (tmp_path / "README").write_text("a repository\n")
    git(tmp_path, "add", "README")
    git(tmp_path, "commit", "--quiet", "-m", "start")
    return tmp_path


def test_a_file_git_does_not_track_is_not_committed(repo: Path) -> None:
    (repo / "prediction.json").write_text("{}")
    with pytest.raises(ValueError, match="is not committed"):
        committed(repo / "prediction.json")


def test_a_committed_file_names_its_commit_until_it_changes(repo: Path) -> None:
    path = repo / "prediction.json"
    path.write_text("{}")
    git(repo, "add", "prediction.json")
    git(repo, "commit", "--quiet", "-m", "predict")
    assert committed(path) == git(repo, "rev-parse", "HEAD")
    path.write_text('{"changed": true}')
    with pytest.raises(ValueError, match="has changed since it was committed"):
        committed(path)


# Both pair qubits measured: 1,000 shots each way, a few misreads.
MEASURED = {
    2: ReadoutCounts(ones_given_0=10, shots_0=1000, zeros_given_1=12, shots_1=1000),
    3: ReadoutCounts(ones_given_0=6, shots_0=1000, zeros_given_1=20, shots_1=1000),
}


def test_the_interval_surrounds_the_prediction_and_reproduces_from_the_choices() -> None:
    choices = tuple(np.random.default_rng(5).integers(0, 4, 4000).tolist())
    first = bell.plan_chsh("fake", CALIBRATION, choices, measured=MEASURED)
    again = bell.plan_chsh("fake", CALIBRATION, choices, measured=MEASURED)
    assert first.interval is not None
    low, high = first.interval
    assert low < first.s < high
    # Sampling at 4,000 rounds alone spans about ±2σ ≈ ±0.09; the inputs widen it.
    assert high - low > 3 * first.standard_error
    assert again.interval == first.interval
    values = first.submission.prediction.values
    assert values["interval"] == [low, high]
    assert "log-uniform" in values["interval_assumptions"]


def test_without_measured_readout_there_is_no_interval() -> None:
    chosen = bell.plan_chsh("fake", CALIBRATION, (0, 1, 2, 3) * 10)
    assert chosen.interval is None
    assert "interval" not in chosen.submission.prediction.values


def test_a_saved_prediction_loads_as_the_same_plan(tmp_path: Path) -> None:
    chosen = bell.plan_chsh("fake", CALIBRATION, (0, 1, 2, 3) * 50, measured=MEASURED)
    path = bell.save_prediction(chosen, tmp_path)
    loaded = bell.load_prediction(path)
    assert loaded.submission == chosen.submission
    assert loaded.interval == chosen.interval


def test_a_prediction_for_another_program_is_refused(tmp_path: Path) -> None:
    chosen = bell.plan_chsh("fake", CALIBRATION, (0, 1, 2, 3) * 50, measured=MEASURED)
    path = bell.save_prediction(chosen, tmp_path)
    data = json.loads(gzip.decompress(path.read_bytes()))
    data["prediction"]["values"]["program_sha256"] = "0" * 64
    path.write_bytes(gzip.compress(json.dumps(data).encode()))
    with pytest.raises(ValueError, match="another program"):
        bell.load_prediction(path)


class Readout(FakeTransport):
    """A readout job with an id of its own: the archive never takes one job twice."""

    def __init__(self, memory: tuple[str, ...], job_id: str) -> None:
        super().__init__(memory)
        self.job_id = job_id

    def run(self, *args: Any, **kwargs: Any) -> JobResult:
        return replace(super().run(*args, **kwargs), job_id=self.job_id)


def readout_runs(directory: Path) -> tuple[Path, Path]:
    """A prepare-|0⟩ and a prepare-|1⟩ run of CALIBRATION's five qubits, a few misreads."""
    zeros = ("00000",) * 95 + ("01000",) * 5
    ones = ("11111",) * 96 + ("11011",) * 4
    runs = []
    for prepare, memory in ((0, zeros), (1, ones)):
        chosen = readout.plan("fake", CALIBRATION, 100, prepare)
        transport = Readout(memory, f"readoutjob{prepare}")
        runs.append(submit(transport, chosen.submission, directory))
    return runs[0], runs[1]


def test_predict_commit_then_submit(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = repo / "runs"
    zero, one = readout_runs(runs)
    transport = SweepTransport(np.random.default_rng(6))
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    predictions = repo / "predictions"
    # The settings come from the pool: two bits a round.
    pool = repo / "pool"
    Pool(pool).add(np.random.default_rng(7).integers(0, 2, 4000), {}, label="settings")
    code, out, err = cli_run(
        [
            "run",
            "chsh",
            "--backend",
            "fake",
            "--rounds",
            "2000",
            "--predict",
            "--readout",
            str(zero),
            str(one),
            "--predictions-dir",
            str(predictions),
            "--pool",
            str(pool),
        ],
        capsys,
    )
    assert code == 0, err
    (path,) = predictions.iterdir()
    assert f"--prediction {path}" in out
    assert transport.rows is None

    submit_argv = ["run", "chsh", "--submit", "--prediction", str(path), "--runs-dir", str(runs)]
    code, _, err = cli_run(submit_argv, capsys)
    assert code == 1
    assert "is not committed" in err
    assert transport.rows is None

    git(repo, "add", str(path))
    git(repo, "commit", "--quiet", "-m", "predict S")
    sha = git(repo, "rev-parse", "HEAD")
    code, out, err = cli_run(submit_argv, capsys)
    assert code == 0, err
    archived = [d for d in runs.iterdir() if (d / "meta.json").exists() and d not in (zero, one)]
    (directory,) = archived
    run = load_run(directory)
    assert run.prediction is not None
    assert run.prediction.values["committed_as"] == sha
    assert run.prediction.written_at < run.submitted_at
    assert "S fell inside it" in out or "S fell outside it" in out
    assert "first half" in out
    assert "second half" in out
    assert f"predicted in commit {sha}" in out


def test_predict_needs_measured_readout(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli_run(
        ["run", "chsh", "--backend", "fake", "--rounds", "100", "--predict"], capsys
    )
    assert code == 2
    assert "--predict needs --readout" in err


def test_submit_needs_a_prediction_file(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli_run(["run", "chsh", "--submit"], capsys)
    assert code == 2
    assert "committed --prediction FILE" in err


@pytest.mark.parametrize(
    ("interval", "verdict"),
    [((2.0, 3.0), "inside"), ((2.9, 3.1), "outside")],
)
def test_the_report_says_whether_s_fell_in_the_interval(
    tmp_path: Path, interval: tuple[float, float], verdict: str
) -> None:
    chosen = bell.plan_chsh("fake", CALIBRATION, (0, 1, 2, 3) * 500, measured=MEASURED)
    values = {**chosen.submission.prediction.values, "interval": list(interval)}
    submission = replace(
        chosen.submission, prediction=replace(chosen.submission.prediction, values=values)
    )
    run = load_run(submit(SweepTransport(np.random.default_rng(8)), submission, tmp_path))
    assert f"S fell {verdict} it" in bell.chsh_report(run)
