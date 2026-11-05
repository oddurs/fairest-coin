from pathlib import Path
from typing import Any

import pytest

from coin import bell, cli
from coin.archive import load_run
from coin.noise import Readout
from tests.test_chsh import CALIBRATION, CZ, READOUT
from tests.test_hardware import FakeTransport
from tests.test_harvest import cli_run


def analytic(pair: tuple[int, int], readout: dict[int, tuple[float, float]]) -> tuple[float, ...]:
    """Agreement and each qubit's P(1) with depolarizing noise and readout only, by hand.

    The Bell pair read in Z has correlation 1 − p and zero marginals; depolarizing p = 4r/3
    keeps that, and each readout maps ±1 to c·z + d on average. So the measured correlation
    is c_A·c_B·(1 − p) + d_A·d_B, agreement is (1 + it)/2, and P(1) = (1 − d)/2 per qubit.
    """
    c = {q: 1 - sum(readout[q]) for q in pair}
    d = {q: readout[q][1] - readout[q][0] for q in pair}
    a, b = pair
    e = c[a] * c[b] * (1 - 4 * CZ[pair] / 3) + d[a] * d[b]
    return (1 + e) / 2, (1 - d[a]) / 2, (1 - d[b]) / 2


def test_the_plan_takes_the_best_pair_and_predicts_its_agreement() -> None:
    chosen = bell.plan("fake", CALIBRATION, 1_000)
    assert chosen.pair == (2, 3)
    agreement, p_a, p_b = analytic((2, 3), READOUT)
    assert chosen.agreement == pytest.approx(agreement, abs=1e-9)
    assert chosen.p_one == pytest.approx((p_a, p_b), abs=1e-9)
    values = chosen.submission.prediction.values
    assert values["purpose"] == "bell"
    assert values["pair"] == [2, 3]
    assert values["agreement"] == chosen.agreement
    assert chosen.submission.layout == (2, 3)


def test_a_named_pair_and_measured_readout_are_used() -> None:
    measured = {1: Readout(0.02, 0.04)}
    chosen = bell.plan("fake", CALIBRATION, 1_000, pair=(1, 0), measured=measured)
    assert chosen.pair == (0, 1)
    assert chosen.readout_source == ("published", "measured")
    readout = {**READOUT, 1: (0.02, 0.04)}
    assert chosen.agreement == pytest.approx(analytic((0, 1), readout)[0], abs=1e-9)


def test_an_uncoupled_pair_is_refused() -> None:
    with pytest.raises(ValueError, match="qubits 0 and 2 are not a coupled pair"):
        bell.plan("fake", CALIBRATION, 1_000, pair=(0, 2))


class BellTransport(FakeTransport):
    def calibration(self, backend: str) -> dict[str, Any]:
        return CALIBRATION


# 90 agreeing shots in 100, both qubits leaning slightly to 1.
SHOTS = ("00",) * 40 + ("11",) * 50 + ("01",) * 5 + ("10",) * 5


def test_coin_run_bell_dry_run_shows_the_circuit_and_cost(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    transport = BellTransport(SHOTS)
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    argv = ["run", "bell", "--backend", "fake", "--shots", "100", "--dry-run"]
    code, out, _ = cli_run([*argv, "--runs-dir", str(tmp_path)], capsys)
    assert code == 0
    assert "pair         2-3" in out
    assert "cz[0, 1]" in out
    assert "QPU seconds" in out
    assert out.rstrip().endswith("dry run: nothing submitted")
    assert transport.submitted == []
    assert not list(tmp_path.iterdir())


def test_coin_run_bell_predicts_first_then_archives_and_reports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    transport = BellTransport(SHOTS)
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    argv = ["run", "bell", "--backend", "fake", "--shots", "100", "--submit"]
    code, out, err = cli_run([*argv, "--runs-dir", str(tmp_path)], capsys)
    assert code == 0, err
    (directory,) = tmp_path.iterdir()
    run = load_run(directory)
    assert run.prediction is not None
    assert run.prediction.written_at < run.submitted_at
    assert run.qubits == (2, 3)
    assert "agreement    90.00% measured" in out
    assert "P(1) on 2    55.00% measured" in out
    assert "P(1) on 3    55.00% measured" in out
    # coin compare reads the same report back from the archive.
    code, compared, _ = cli_run(["compare", str(directory)], capsys)
    assert code == 0
    assert compared.splitlines()[1:] == out.splitlines()[-3:]


@pytest.mark.parametrize(
    ("agreeing", "verdict"),
    [(97, "z = -0.3 (within 3σ)"), (90, "z = -4.8 (outside 3σ)")],  # noqa: RUF001 - display text
)
def test_the_report_says_whether_each_rate_is_within_three_sigma(
    tmp_path: Path, agreeing: int, verdict: str
) -> None:
    from coin.hardware import submit  # noqa: PLC0415

    # Predicted agreement is 97.52%: σ = 1.56% at 100 shots.
    shots = ("00",) * agreeing + ("01",) * (100 - agreeing)
    chosen = bell.plan("fake", CALIBRATION, 100)
    run = load_run(submit(BellTransport(shots), chosen.submission, tmp_path))
    line = bell.report(run).splitlines()[1]
    assert line.startswith(f"agreement    {agreeing:.2f}% measured, 97.52% predicted")
    assert line.endswith(verdict)


def test_report_refuses_a_run_that_is_not_a_bell_run() -> None:
    first = load_run(Path(__file__).parent.parent / "data/runs/2026-11-01-dbjsk29ffo6c73baaosg")
    with pytest.raises(ValueError, match="not a Bell run"):
        bell.report(first)
