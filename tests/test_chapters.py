"""The chapters quote code and show commands; these tests stop either drifting from the repo.

- `>>>` examples inside ```pycon blocks run as doctests.
- A ```python block preceded by `<!-- from: PATH -->` must appear verbatim in PATH.
- Every `$ coin ...` and `$ uv run python analysis/...` line in a ```console block is
  run, and its output must match the lines that follow it, up to the next `$` line.
"""

import doctest
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from coin import __version__
from coin.cli import main

ROOT = Path(__file__).resolve().parent.parent
# The README quotes commands too, so it is held to the same standard as a chapter.
CHAPTERS = [ROOT / "README.md", *sorted((ROOT / "docs" / "chapters").glob("*.md"))]

EXCERPT = re.compile(r"<!-- from: (?P<path>\S+) -->\n```python\n(?P<code>.*?)```", re.S)
PYCON = re.compile(r"```pycon\n(.*?)```", re.S)
CONSOLE = re.compile(r"```console\n(?P<body>.*?)```", re.S)
# A `$ ` line, then everything up to the next `$ ` line or the end of the block.
PROMPT = re.compile(r"^\$ (.+)\n((?:(?!\$ ).*\n)*)", re.M)


def ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


@pytest.mark.parametrize("chapter", CHAPTERS, ids=ids(CHAPTERS))
def test_examples_run(chapter: Path) -> None:
    # Only the inside of ```pycon blocks, so a closing fence is never read as expected output.
    # Blocks share one namespace, in order, as they would for a reader typing along.
    source = "\n".join(PYCON.findall(chapter.read_text()))
    test = doctest.DocTestParser().get_doctest(source, {}, chapter.stem, str(chapter), 0)
    runner = doctest.DocTestRunner(optionflags=doctest.NORMALIZE_WHITESPACE)
    runner.run(test)
    assert runner.failures == 0, f"{runner.failures} example(s) failed in {chapter.name}"


@pytest.mark.parametrize("chapter", CHAPTERS, ids=ids(CHAPTERS))
def test_excerpts_match_the_source(chapter: Path) -> None:
    for match in EXCERPT.finditer(chapter.read_text()):
        source = (ROOT / match["path"]).read_text()
        assert match["code"] in source, f"excerpt from {match['path']} no longer matches"


def run_coin(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    try:
        code = main(argv)
    except SystemExit as exit_info:  # argparse exits for --help and --version
        code = int(exit_info.code or 0)
    return code, capsys.readouterr().out


ANALYSIS = ["uv", "run", "python"]


def run_analysis(argv: list[str]) -> tuple[int, str]:
    # The suite already runs inside the project's environment: no need for uv again.
    assert argv[0].startswith("analysis/"), f"only analysis scripts can be checked: {argv}"
    done = subprocess.run(
        [sys.executable, *argv], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout


def check_console(text: str, capsys: pytest.CaptureFixture[str]) -> int:
    """Run every command in every console block; return how many were checked.

    A command's expected output is every line after it, up to the next `$` line.
    """
    checked = 0
    for block in CONSOLE.finditer(text):
        for command, expected in PROMPT.findall(block["body"]):
            argv = shlex.split(command)
            if argv[:3] == ANALYSIS:
                result = run_analysis(argv[3:])
            else:
                assert argv[0] == "coin", f"only `coin` and analysis commands run: {command}"
                result = run_coin(argv[1:], capsys)
            assert result == (0, expected), f"`$ {command}` disagrees"
            checked += 1
    return checked


@pytest.mark.parametrize("chapter", CHAPTERS, ids=ids(CHAPTERS))
def test_commands_print_what_the_chapter_says(
    chapter: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    check_console(chapter.read_text(), capsys)


def test_every_command_in_a_block_is_checked(capsys: pytest.CaptureFixture[str]) -> None:
    flip = run_coin(["flip", "--sim", "--seed", "1"], capsys)[1]
    text = (
        f"```console\n$ coin flip --sim --seed 1\n{flip}$ coin --version\ncoin {__version__}\n```\n"
    )
    assert check_console(text, capsys) == 2


def test_a_wrong_second_command_is_caught(capsys: pytest.CaptureFixture[str]) -> None:
    text = "```console\n$ coin --version\ncoin 0.0.0-not-this\n```\n"
    with pytest.raises(AssertionError, match="disagrees"):
        check_console(text, capsys)


def test_an_analysis_script_in_a_block_is_checked(capsys: pytest.CaptureFixture[str]) -> None:
    run = "data/runs/2026-11-01-dbjsk29ffo6c73baaosg"
    command = f"uv run python analysis/dominant_errors.py {run}"
    wrong = f"```console\n$ {command}\nnothing like this\n```\n"
    with pytest.raises(AssertionError, match="disagrees"):
        check_console(wrong, capsys)


def test_no_chapter_shows_output_the_suite_does_not_check() -> None:
    # A ```text block of command output would escape the checks above.
    for chapter in CHAPTERS:
        assert "```text\n$ " not in chapter.read_text(), chapter.name
