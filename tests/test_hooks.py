"""The commit-msg hook is the only thing between a bad subject and `main`; pin its behaviour."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".githooks" / "commit-msg"


def run_hook(tmp_path: Path, message: str) -> subprocess.CompletedProcess[str]:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(message + "\n")
    return subprocess.run([HOOK, msg], capture_output=True, text=True, cwd=ROOT, check=False)


@pytest.mark.parametrize(
    "message",
    [
        "feat(sim): simulate circuits as statevectors",
        "fix!: change the outcome order",
        "docs: update CLAUDE.md for the new workflow",
        "chore(deps): bump numpy\n\nRefs: 0008",
        "Merge branch 'main' into feat/x",
        "test: " + "a" * 66,  # exactly 72 characters, the limit
    ],
)
def test_accepts(tmp_path: Path, message: str) -> None:
    result = run_hook(tmp_path, message)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("Added the simulator", "not a Conventional Commit"),
        ("feature: add the simulator", "not a Conventional Commit"),
        ("feat:missing space", "not a Conventional Commit"),
        ("feat: add the simulator.", "ends with a period"),
        ("test: " + "a" * 67, "limit is 72"),
        ("chore: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>", "attribution"),
        ("chore: x\n\n🤖 Generated with a tool", "attribution"),
        ("docs: x\n\nWritten with Claude Code", "attribution"),
    ],
)
def test_rejects(tmp_path: Path, message: str, reason: str) -> None:
    result = run_hook(tmp_path, message)
    assert result.returncode == 1
    assert reason in result.stderr
