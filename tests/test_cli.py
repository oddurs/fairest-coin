import argparse

import pytest

from coin import __version__, cli
from coin.cli import main


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


def test_hardware_flip_explains_sim(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(["flip"], capsys)
    assert code == 2
    assert out == ""
    assert "--sim" in err


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
