"""Hypothesis runs the same examples every time unless asked to explore.

A property test that fails on a rare random input and passes on the retry is a flaky test,
and a red CI run nobody can reproduce. So the default profile is derandomized, with no
example database. Set HYPOTHESIS_PROFILE=explore to search randomly; a failure found that
way is turned into a fixed test case.
"""

import os

from hypothesis import settings

settings.register_profile("deterministic", derandomize=True, database=None)
settings.register_profile("explore", derandomize=False, max_examples=1000)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "deterministic"))
