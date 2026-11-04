"""Writes that survive a power cut.

A file's bytes are durable once the drive has them, and a new name (a created file, a
rename) once its directory is synced too. The pool, the archive and the pending record
all write through here, so a power cut can never keep one and lose the other.
"""

import fcntl
import os
from pathlib import Path


def sync(descriptor: int) -> None:
    """Ask the drive itself to hold what `descriptor` has written."""
    # On macOS fsync leaves the data in the drive's cache; F_FULLFSYNC asks the drive to
    # write it. Elsewhere fsync is the strongest there is.
    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        try:
            fcntl.fcntl(descriptor, full)
            return
        except OSError:
            pass  # the filesystem does not support it; fsync below still applies
    os.fsync(descriptor)


def sync_directory(path: Path) -> None:
    """Make the names in `path` (new files, renames, removals) durable."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        sync(descriptor)
    finally:
        os.close(descriptor)


def make_directory(path: Path) -> None:
    """Create `path` and any missing parents, each one's name made durable."""
    missing = [p for p in (path, *path.parents) if not p.exists()]
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        sync_directory(directory.parent)
    path.mkdir(exist_ok=True)  # a file in the way raises FileExistsError, as mkdir would


def write(path: Path, data: bytes, mode: int = 0o644) -> None:
    """Write `data` to `path` and sync it. The name is durable only once the caller syncs
    the directory, which lets a caller writing many files sync it once. A new file gets
    `mode` (less the umask)."""
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode), "wb") as handle:
        handle.write(data)
        handle.flush()
        sync(handle.fileno())


def replace(path: Path, data: bytes, mode: int = 0o644) -> None:
    """Put `data` at `path` whole or not at all, durably: a synced temporary file renamed
    over it, then the directory synced. The file gets `mode` (less the umask)."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.unlink(missing_ok=True)  # a leftover would keep its own mode
    write(temporary, data, mode)
    temporary.replace(path)
    sync_directory(path.parent)
