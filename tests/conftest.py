"""Hypothesis runs the same examples every time unless asked to explore.

A property test that fails on a rare random input and passes on the retry is a flaky test,
and a red CI run nobody can reproduce. So the default profile is derandomized, with no
example database. Set HYPOTHESIS_PROFILE=explore to search randomly; a failure found that
way is turned into a fixed test case.

No deadline either: Qiskit's first QASM parse costs 50-100 ms cold and under 1 ms warm, so
under load it can exceed hypothesis's 200 ms deadline once and pass on replay. That was the
compile suite's unexplained failure. A per-example wall-clock limit is itself a flake.
"""

import os

import pytest
from hypothesis import settings

settings.register_profile("deterministic", derandomize=True, database=None, deadline=None)
settings.register_profile("explore", derandomize=False, max_examples=1000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "deterministic"))


@pytest.fixture(autouse=True)
def private_pool(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test gets its own empty entropy pool; none can touch the user's."""
    monkeypatch.setenv("COIN_POOL", str(tmp_path_factory.mktemp("pool")))
