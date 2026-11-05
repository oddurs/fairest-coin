"""Which record recovery trusts, and when it stops: the cases the v0.3 mutants found open."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from coin.archive import Run, load_run
from coin.hardware import recover, submit
from tests.test_hardware import NoFetch, Submits, plan


def test_recovery_prefers_the_record_that_already_holds_the_shots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An interrupted archive leaves a record with the result. A newer copy without it must
    # not win: fetching again is a second chance to fail, and needs a connection.
    def interrupted(*_args: Any, **_kwargs: Any) -> Path:
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr("coin.hardware.write_run", interrupted)
        with pytest.raises(KeyboardInterrupt):
            submit(Submits(), plan(), tmp_path)
    (with_result,) = tmp_path.glob(".pending-*.json")
    record = json.loads(with_result.read_text())
    del record["result"]
    newer = tmp_path / ".pending-ffff.json"
    newer.write_text(json.dumps(record))
    later = with_result.stat().st_mtime + 60
    os.utime(newer, (later, later))
    run = load_run(recover(NoFetch, "jobX", tmp_path))
    assert run.memory == ("0", "1", "1", "0")
    assert not list(tmp_path.glob(".pending-*"))


def test_an_interruption_is_never_mistaken_for_a_lost_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Another archiver finished first, and then Ctrl-C arrived: the interruption still
    # stops the program, rather than being swallowed as a race this run lost.
    def raced_then_interrupted(runs_dir: Path, run: Run, **_kwargs: Any) -> Path:
        (Path(runs_dir) / run.directory_name).mkdir()
        raise KeyboardInterrupt

    monkeypatch.setattr("coin.hardware.write_run", raced_then_interrupted)
    with pytest.raises(KeyboardInterrupt):
        submit(Submits(), plan(), tmp_path)
