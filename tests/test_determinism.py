import os
import subprocess
import sys
from pathlib import Path

from hypothesis import settings

ROOT = Path(__file__).resolve().parent.parent

# Loads the project's profile, then records every example one property test is given.
DRAW = """
import tests.conftest
from hypothesis import given, strategies as st
seen = []
@given(st.lists(st.floats(allow_nan=False), max_size=5))
def prop(xs):
    seen.append(xs)
prop()
print(repr(seen))
"""


def draws(profile: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "HYPOTHESIS_PROFILE"}
    if profile is not None:
        env["HYPOTHESIS_PROFILE"] = profile
    result = subprocess.run(
        [sys.executable, "-c", DRAW], cwd=ROOT, env=env, capture_output=True, text=True, check=True
    )
    return result.stdout


def test_property_tests_draw_the_same_examples_every_run() -> None:
    assert draws(None) == draws(None)


def test_no_example_has_a_wall_clock_deadline() -> None:
    assert settings().deadline is None
