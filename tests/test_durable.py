"""Every write the project relies on reaches the drive, names included, before it is used."""

import fcntl
import os
from pathlib import Path
from typing import Any

import pytest

import coin.durable
from coin import archive, durable
from coin.hardware import JobResult
from coin.pool import Pool
from tests.test_hardware import FakeTransport, go

FULLFSYNC = 51  # macOS's value; any number will do where the platform lacks it


class Syncs:
    """Records, in order, every synced inode, rename and unlink."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.events: list[tuple[str, object]] = []
        real_sync, real_unlink = durable.sync, os.unlink
        real_rename, real_replace = os.rename, os.replace

        def sync(descriptor: int) -> None:
            self.events.append(("sync", os.fstat(descriptor).st_ino))
            real_sync(descriptor)

        def renamer(real: object) -> object:
            def rename(source: object, target: object) -> None:
                real(source, target)  # ty: ignore[call-non-callable]
                self.events.append(("rename", Path(str(target))))

            return rename

        def unlink(path: object, *args: object, **kwargs: object) -> None:
            self.events.append(("unlink", Path(str(path))))
            real_unlink(path, *args, **kwargs)  # ty: ignore[invalid-argument-type]

        monkeypatch.setattr(coin.durable, "sync", sync)
        monkeypatch.setattr(os, "rename", renamer(real_rename))
        monkeypatch.setattr(os, "replace", renamer(real_replace))
        monkeypatch.setattr(os, "unlink", unlink)

    @property
    def synced(self) -> set[object]:
        return {inode for kind, inode in self.events if kind == "sync"}

    def index(self, event: tuple[str, object]) -> int:
        return max(i for i, e in enumerate(self.events) if e == event)


def inode(path: Path) -> int:
    return path.stat().st_ino


def test_sync_asks_the_drive_with_fullfsync_where_it_can(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(fcntl, "F_FULLFSYNC", FULLFSYNC, raising=False)
    monkeypatch.setattr(fcntl, "fcntl", lambda fd, op: calls.append(("fcntl", op)))
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append("fsync"))
    durable.sync(0)
    assert calls == [("fcntl", FULLFSYNC)]


def test_sync_falls_back_to_fsync_when_fullfsync_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def refuse(fd: int, op: int) -> None:
        raise OSError("not supported by this filesystem")

    monkeypatch.setattr(fcntl, "F_FULLFSYNC", FULLFSYNC, raising=False)
    monkeypatch.setattr(fcntl, "fcntl", refuse)
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append("fsync"))
    durable.sync(0)
    assert calls == ["fsync"]


def test_sync_uses_fsync_where_there_is_no_fullfsync(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.delattr(fcntl, "F_FULLFSYNC", raising=False)
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append("fsync"))
    durable.sync(0)
    assert calls == ["fsync"]


def test_replace_syncs_the_file_then_its_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    syncs = Syncs(monkeypatch)
    target = tmp_path / "spent.json"
    durable.replace(target, b"{}")
    assert target.read_bytes() == b"{}"
    assert [p.name for p in tmp_path.iterdir()] == ["spent.json"]
    events = [e for e in syncs.events if e[0] != "unlink"]
    assert events == [("sync", inode(target)), ("rename", target), ("sync", inode(tmp_path))]


def test_the_pool_syncs_every_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    syncs = Syncs(monkeypatch)
    pool = Pool(tmp_path / "pool")
    pool.add([1, 0, 1], {}, label="a")
    pool.take(1)
    files = [p for p in (tmp_path / "pool").iterdir() if not p.name.startswith(".")]
    assert {f.suffix for f in files} >= {".json", ".bits"}
    # The lock file holds nothing; every file that holds bits or counts is synced.
    held = {inode(f) for f in files if f.name != "lock"}
    assert held | {inode(tmp_path / "pool"), inode(tmp_path)} <= syncs.synced


def test_an_archived_run_is_durable_before_its_pending_record_goes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    syncs = Syncs(monkeypatch)
    run_dir = go(FakeTransport(("0", "1", "1", "0")), tmp_path)
    (pending,) = [
        p
        for kind, p in syncs.events
        if kind == "unlink"
        and isinstance(p, Path)
        and p.name.startswith(".pending-")
        and p.suffix == ".json"
    ]
    gone = syncs.index(("unlink", pending))
    before = {inode for kind, inode in syncs.events[:gone] if kind == "sync"}
    # Every file, the run's directory, and the runs directory after the rename.
    assert {inode(f) for f in run_dir.iterdir()} | {inode(run_dir)} <= before
    renamed = syncs.index(("rename", run_dir))
    assert ("sync", inode(tmp_path)) in syncs.events[renamed:gone]


def test_a_new_runs_directory_is_itself_made_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    syncs = Syncs(monkeypatch)
    run_dir = go(FakeTransport(("0", "1")), tmp_path / "runs", shots=2)
    assert run_dir.parent == tmp_path / "runs"
    assert inode(tmp_path) in syncs.synced


def test_an_added_record_is_durable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = go(FakeTransport(("0", "1")), tmp_path, shots=2)
    syncs = Syncs(monkeypatch)
    record = archive.add_record(run_dir, archive.EXTRACTION, {"bits": 1})
    assert {inode(record), inode(run_dir)} <= syncs.synced
    assert not [p for p in run_dir.iterdir() if p.name.startswith(".")]


def test_the_pending_record_is_durable_before_the_job_is_submitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    syncs = Syncs(monkeypatch)
    seen: list[bool] = []

    class Checks(FakeTransport):
        def run(self, *args: Any, **kwargs: Any) -> JobResult:
            # From here the QPU time may be spent: the prediction must already be safe.
            (record,) = tmp_path.glob(".pending-*.json")
            seen.append({inode(record), inode(tmp_path)} <= syncs.synced)
            return super().run(*args, **kwargs)

    go(Checks(("0", "1")), tmp_path, shots=2)
    assert seen == [True]
