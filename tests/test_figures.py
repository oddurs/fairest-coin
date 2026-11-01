import subprocess
import sys
from pathlib import Path

import pytest

from coin import figures

ROOT = Path(__file__).parent.parent
RUNS = ROOT / "data" / "runs"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("figures")
    figures.render(RUNS, out)
    return out


@pytest.fixture
def committed(rendered: Path, tmp_path: Path) -> Path:
    """A copy of a fresh render, standing in for docs/figures, that a test may damage."""
    out = tmp_path / "figures"
    out.mkdir()
    for path in rendered.iterdir():
        (out / path.name).write_bytes(path.read_bytes())
    return out


def test_renders_every_registered_figure(rendered: Path) -> None:
    assert sorted(p.name for p in rendered.iterdir()) == sorted(figures.FIGURES)


def test_rendering_twice_gives_identical_bytes(rendered: Path, tmp_path: Path) -> None:
    figures.render(RUNS, tmp_path)
    for path in rendered.iterdir():
        assert (tmp_path / path.name).read_bytes() == path.read_bytes(), path.name


def test_svg_has_no_date_and_keeps_text_as_text(rendered: Path) -> None:
    svg = (rendered / "first-coin.svg").read_text()
    assert "<dc:date>" not in svg
    assert "<text" in svg
    assert "dbjsk29ffo6c73baaosg" in svg


def test_first_coin_reports_the_archived_numbers(rendered: Path) -> None:
    svg = (rendered / "first-coin.svg").read_text()
    # 2071 of 4096 tails; the prediction's p_tails and sigma_tails / shots, to 4 places.
    assert "0.5056 ± 0.0078" in svg
    assert "0.4995 ± 0.0078" in svg
    assert "ibm_marrakesh" in svg
    assert "qubit 139" in svg


def test_check_passes_on_a_fresh_render(committed: Path) -> None:
    assert figures.check(RUNS, committed) == []


def test_check_names_an_altered_figure(committed: Path) -> None:
    path = committed / "first-coin.svg"
    path.write_bytes(path.read_bytes().replace(b"measured", b"measureD", 1))
    (problem,) = figures.check(RUNS, committed)
    assert str(path) in problem
    assert "differs" in problem


def test_check_names_a_missing_figure(committed: Path) -> None:
    path = committed / "first-coin.svg"
    path.unlink()
    (problem,) = figures.check(RUNS, committed)
    assert str(path) in problem
    assert "missing" in problem


def test_check_names_an_extra_file(committed: Path) -> None:
    path = committed / "stale.svg"
    path.write_text("<svg/>")
    (problem,) = figures.check(RUNS, committed)
    assert str(path) in problem


def test_main_check_exits_non_zero_and_names_the_file(
    committed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (committed / "first-coin.svg").write_text("<svg/>")
    assert figures.main(["--check", "--runs", str(RUNS), "--out", str(committed)]) == 1
    assert "first-coin.svg" in capsys.readouterr().err


def test_main_check_exits_zero_when_figures_match(committed: Path) -> None:
    assert figures.main(["--check", "--runs", str(RUNS), "--out", str(committed)]) == 0


def test_main_writes_figures(tmp_path: Path, rendered: Path) -> None:
    assert figures.main(["--runs", str(RUNS), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "first-coin.svg").read_bytes() == (rendered / "first-coin.svg").read_bytes()


def test_importing_coin_does_not_load_matplotlib() -> None:
    # A fresh interpreter: this one has already imported matplotlib through coin.figures.
    code = (
        "import pkgutil, importlib, sys, coin\n"
        "for m in pkgutil.iter_modules(coin.__path__):\n"
        "    if m.name != 'figures': importlib.import_module('coin.' + m.name)\n"
        "assert 'matplotlib' not in sys.modules, 'matplotlib was imported'\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
