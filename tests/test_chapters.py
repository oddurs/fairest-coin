"""The chapters quote code and show commands; these tests stop either drifting from the repo.

- `>>>` examples inside ```pycon blocks run as doctests.
- A ```python block preceded by `<!-- from: PATH -->` must appear verbatim in PATH.
- A ```console block's `$ coin ...` lines are run, and the output must match what follows.
"""

import doctest
import re
import shlex
from pathlib import Path

import pytest

from coin.cli import main

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS = sorted((ROOT / "docs" / "chapters").glob("*.md"))

EXCERPT = re.compile(r"<!-- from: (?P<path>\S+) -->\n```python\n(?P<code>.*?)```", re.S)
PYCON = re.compile(r"```pycon\n(.*?)```", re.S)
CONSOLE = re.compile(r"```console\n(?P<body>.*?)```", re.S)


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


@pytest.mark.parametrize("chapter", CHAPTERS, ids=ids(CHAPTERS))
def test_commands_print_what_the_chapter_says(
    chapter: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for block in CONSOLE.finditer(chapter.read_text()):
        command, _, expected = block["body"].partition("\n")
        argv = shlex.split(command.removeprefix("$ "))
        assert argv[0] == "coin", f"only `coin` commands can be checked: {command}"
        assert main(argv[1:]) == 0
        assert capsys.readouterr().out == expected, f"`{command}` printed something else"
