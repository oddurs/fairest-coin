"""`scripts/agent start` shares the clone's local, untracked files with each new worktree."""

import os
import subprocess
from pathlib import Path

import pytest

AGENT = Path(__file__).resolve().parent.parent / "scripts" / "agent"

EXCLUDE = """\
# local to this clone
/LOCAL.md
.tool
*.log
!keep.log
absent.md
README.md
"""


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=_env(), capture_output=True, text=True, check=True
    ).stdout


def _env() -> dict[str, str]:
    # A git hook runs this suite with GIT_DIR set; the scratch repos must not inherit it,
    # nor the owner's global config and hooks.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return env | {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }


def _clone(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    git("init", "--quiet", "--bare", "--initial-branch=main", str(origin), cwd=tmp_path)
    clone = tmp_path / "repo"
    git("clone", "--quiet", str(origin), str(clone), cwd=tmp_path)
    (clone / "README.md").write_text("tracked\n")
    git("add", "README.md", cwd=clone)
    git("commit", "--quiet", "-m", "chore: start", cwd=clone)
    git("push", "--quiet", "origin", "HEAD:main", cwd=clone)
    git("remote", "set-head", "origin", "main", cwd=clone)
    return clone


def _start(clone: Path) -> Path:
    result = subprocess.run(
        [str(AGENT), "start", "chore/x"],
        cwd=clone,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.splitlines()[-1])


def test_start_links_the_clones_local_files_into_the_worktree(tmp_path: Path) -> None:
    clone = _clone(tmp_path)
    (clone / ".git" / "info" / "exclude").write_text(EXCLUDE)
    (clone / "LOCAL.md").write_text("local instructions\n")
    (clone / ".tool" / "rules").mkdir(parents=True)
    (clone / ".tool" / "rules" / "a.md").write_text("a rule\n")
    (clone / "debug.log").write_text("not linked: a glob\n")

    tree = _start(clone)
    assert tree == tmp_path / ".worktrees" / "repo" / "chore" / "x"

    assert (tree / "LOCAL.md").readlink() == clone / "LOCAL.md"
    assert (tree / ".tool" / "rules" / "a.md").read_text() == "a rule\n"
    assert not (tree / "debug.log").exists()
    assert not (tree / "absent.md").exists()
    # A tracked file the worktree already has is never replaced by a link.
    assert not (tree / "README.md").is_symlink()
    # The links are excluded too, so the worktree is clean and `done` may remove it.
    assert git("status", "--porcelain", cwd=tree) == ""

    git("worktree", "remove", str(tree), cwd=clone)
    assert (clone / "LOCAL.md").read_text() == "local instructions\n"
    assert (clone / ".tool" / "rules" / "a.md").exists()


@pytest.mark.parametrize("missing", [False, True], ids=["git's default", "missing"])
def test_start_with_nothing_excluded_links_nothing(tmp_path: Path, missing: bool) -> None:
    clone = _clone(tmp_path)
    exclude = clone / ".git" / "info" / "exclude"
    assert exclude.read_text().lstrip().startswith("#")  # git's template: comments only
    if missing:
        exclude.unlink()
    tree = _start(clone)
    assert sorted(p.name for p in tree.iterdir()) == [".git", "README.md"]
