import argparse
from pathlib import Path

import pytest

from coin import __version__, cli
from coin.cli import main
from coin.sim import probabilities


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    try:
        code = main(argv)
    except SystemExit as exit_info:  # argparse exits for --help, --version and usage errors
        code = int(exit_info.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["--version"], capsys) == (0, f"coin {__version__}\n", "")


def test_single_flip_prints_one_face(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["flip", "--sim"], capsys)
    assert code == 0
    assert out in {"HEADS\n", "TAILS\n"}


def test_unseeded_flips_are_not_constant(capsys: pytest.CaptureFixture[str]) -> None:
    # 64 identical fair flips happen with probability 2⁻⁶³; seen, the seed is stuck.
    faces = {run(["flip", "--sim"], capsys)[1] for _ in range(64)}
    assert faces == {"HEADS\n", "TAILS\n"}


def test_seeded_flip_replays(capsys: pytest.CaptureFixture[str]) -> None:
    first = run(["flip", "--sim", "--seed", "42"], capsys)
    assert run(["flip", "--sim", "--seed", "42"], capsys) == first


def test_shots_snapshot(capsys: pytest.CaptureFixture[str]) -> None:
    # Pinned from a real run; chapter 1 quotes this exact output.
    code, out, _ = run(["flip", "--sim", "--shots", "10000", "--seed", "1"], capsys)
    assert code == 0
    assert out == "heads   4,971   49.71%\ntails   5,029   50.29%\n"


def test_shots_columns_align_for_small_counts(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["flip", "--sim", "--shots", "1", "--seed", "3"], capsys)
    assert code == 0
    assert out in {
        "heads  1  100.00%\ntails  0    0.00%\n",
        "heads  0    0.00%\ntails  1  100.00%\n",
    }


@pytest.mark.parametrize("shots", ["0", "-3", "ten"])
def test_bad_shots_are_rejected(shots: str, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(["flip", "--sim", "--shots", shots], capsys)
    assert code == 2
    assert "--shots" in err


@pytest.mark.parametrize("seed", ["-1", "x"])
def test_bad_seed_is_a_usage_error_not_a_crash(
    seed: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run(["flip", "--sim", "--seed", seed], capsys)
    assert code == 2
    assert "--seed" in err


def test_no_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run([], capsys)
    assert code == 2
    assert "COMMAND" in err


@pytest.mark.parametrize("argv", [["--help"], ["flip", "--help"]])
def test_help_describes_every_flag(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(argv, capsys)
    assert code == 0
    expected = ["flip", "--version"] if argv == ["--help"] else ["--sim", "--shots", "--seed"]
    for flag in expected:
        assert flag in out


def test_each_subcommand_reaches_its_own_handler(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A second subcommand must not fall through to the flip logic.
    build = cli._parser

    def with_probe() -> argparse.ArgumentParser:
        parser = build()
        commands = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        commands.add_parser("probe").set_defaults(handler=lambda _args: 7)
        return parser

    monkeypatch.setattr(cli, "_parser", with_probe)
    assert run(["probe"], capsys)[0] == 7
    assert run(["flip", "--sim", "--seed", "1"], capsys)[0] == 0


FIRST_RUN = "data/runs/2026-11-01-dbjsk29ffo6c73baaosg"


def test_native_coin_is_the_coin() -> None:
    # The hand-lowered coin must be H up to global phase: same outcome probabilities.
    assert probabilities(cli.NATIVE_COIN) == pytest.approx(probabilities(cli.COIN), abs=1e-12)


def test_predict_lists_every_qubit_sorted_and_reports_exclusions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out, _ = run(["predict", "--calibration", FIRST_RUN], capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[0].split() == ["qubit", "P(tails)", "bias"]
    rows = [line.split() for line in lines[1:] if "excluded" not in line]
    assert len(rows) == 149
    tails = [float(row[1]) for row in rows]
    assert tails == sorted(tails)
    excluded = [line for line in lines if "excluded" in line]
    assert [line.split()[0] for line in excluded] == ["20", "82", "83", "94", "113", "119", "130"]
    assert "68.50 µs exceeds 2·T1 = 68.46 µs" in excluded[0]


def test_predict_with_measurement_decay_predicts_more_heads(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def tails_by_qubit(argv: list[str]) -> dict[str, float]:
        out = run(argv, capsys)[1]
        return {r.split()[0]: float(r.split()[1]) for r in out.splitlines()[1:] if "excl" not in r}

    base = tails_by_qubit(["predict", "--calibration", FIRST_RUN])
    decay = tails_by_qubit(["predict", "--calibration", FIRST_RUN, "--measurement-decay"])
    assert all(decay[q] < base[q] for q in base)


@pytest.mark.parametrize("path", ["/no/such/file.json", "tests"])
def test_predict_with_unreadable_calibration_fails_cleanly(
    path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run(["predict", "--calibration", path], capsys)
    assert code == 1
    assert out == ""
    assert "cannot read calibration" in err


@pytest.mark.parametrize("content", ["[]", '{"qubits": []}', '{"gates": [], "qubits": 3}'])
def test_predict_with_content_that_is_not_a_snapshot_fails_cleanly(
    content: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "calibration.json"
    bad.write_text(content)
    code, out, err = run(["predict", "--calibration", str(bad)], capsys)
    assert code == 1
    assert out == ""
    assert "not a calibration snapshot" in err
