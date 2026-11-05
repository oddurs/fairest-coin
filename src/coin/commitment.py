"""A prediction committed to git before its run, so the order can be checked by anyone.

A prediction file on disk proves nothing about when it was written: it could be edited after
the result came in. Committed and pushed, it has a place in a history whose order is public.
`committed` refuses a file git does not track, or one changed since its last commit, and
names the commit that holds it, which the run then records.
"""

import os
import subprocess
from pathlib import Path


def committed(path: Path) -> str:
    """The commit that last changed `path`, which must be tracked and unchanged since.

    Raises ValueError saying what to do otherwise.
    """
    where = path.resolve()
    if not where.is_file():
        raise ValueError(f"{path} does not exist")
    # Git's own variables (set, for one, while a hook runs) would point it at another
    # repository than the one `path` is in.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=where.parent, capture_output=True, text=True, check=False, env=env
        )

    if git("ls-files", "--error-unmatch", "--", str(where)).returncode != 0:
        raise ValueError(f"{path} is not committed; commit and push it, then submit")
    if git("diff", "--quiet", "HEAD", "--", str(where)).returncode != 0:
        raise ValueError(f"{path} has changed since it was committed; commit it again")
    found = git("log", "-1", "--format=%H", "--", str(where))
    if found.returncode != 0 or not found.stdout.strip():
        raise ValueError(f"git could not say which commit holds {path}: {found.stderr.strip()}")
    return found.stdout.strip()
