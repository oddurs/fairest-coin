import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SLOW = """
import time

def test_slow():
    time.sleep(3)
"""


def test_the_suite_dumps_a_stack_for_any_test_that_runs_too_long() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert config["tool"]["pytest"]["ini_options"]["faulthandler_timeout"] == 300


def test_faulthandler_timeout_names_the_hanging_test(tmp_path: Path) -> None:
    # The mechanism the setting relies on, shown on a test that outlives a 1 s timeout.
    (tmp_path / "test_slow.py").write_text(SLOW)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "faulthandler_timeout=1",
            str(tmp_path / "test_slow.py"),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert "Timeout" in result.stderr
    assert "test_slow" in result.stderr
