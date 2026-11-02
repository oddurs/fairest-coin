import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import coin.pool
from coin.pool import POOL_ENV, EmptyPoolError, Pool, default_path


def filled(path: Path, *sizes: int) -> Pool:
    pool = Pool(path)
    for i, size in enumerate(sizes):
        pool.add(np.arange(size) % 2, {"job_id": f"job{i}"}, label=f"job{i}")
    return pool


def test_bits_come_back_as_they_went_in_oldest_batch_first(tmp_path: Path) -> None:
    pool = Pool(tmp_path)
    pool.add([1, 0, 1], {"job_id": "a"}, label="a")
    draws = pool.take(3)
    assert [d.bits.tolist() for d in draws] == [[1, 0, 1]]
    assert (draws[0].offset, draws[0].provenance["job_id"]) == (0, "a")


def test_a_take_can_span_batches(tmp_path: Path) -> None:
    pool = Pool(tmp_path)
    pool.add([1, 1], {}, label="a")
    pool.add([0, 0, 0], {}, label="b")
    draws = pool.take(4)
    assert [
        (d.batch.endswith(x), d.offset, len(d.bits)) for d, x in zip(draws, "ab", strict=True)
    ] == [
        (True, 0, 2),
        (True, 0, 2),
    ]
    assert [len(d.bits) for d in pool.take(1)] == [1]


def test_a_spent_bit_is_never_returned_again(tmp_path: Path) -> None:
    pool = filled(tmp_path, 10)
    first = pool.take(4)
    second = Pool(tmp_path).take(6)  # a fresh handle, as a new process would have
    assert first[0].offset == 0
    assert second[0].offset == 4
    with pytest.raises(EmptyPoolError):
        pool.take(1)


def test_an_empty_pool_says_to_harvest(tmp_path: Path) -> None:
    with pytest.raises(EmptyPoolError, match="run `coin harvest`"):
        Pool(tmp_path).take(1)


def test_asking_for_more_than_remains_spends_nothing(tmp_path: Path) -> None:
    pool = filled(tmp_path, 5)
    with pytest.raises(EmptyPoolError, match="5 unspent"):
        pool.take(6)
    assert [s.remaining for s in pool.status()] == [5]


def test_status_shows_remaining_bits_per_batch(tmp_path: Path) -> None:
    pool = filled(tmp_path, 8, 4)
    pool.take(10)
    assert [(s.total, s.spent, s.remaining) for s in pool.status()] == [(8, 8, 0), (4, 2, 2)]
    assert pool.status()[1].provenance["job_id"] == "job1"
    assert Pool(tmp_path / "nowhere").status() == []


# Each worker takes one bit at a time until the pool is empty, and prints where each came
# from. If locking failed, two workers would print the same (batch, offset).
WORKER = """
import sys
from coin.pool import EmptyPoolError, Pool
pool = Pool(__import__("pathlib").Path(sys.argv[1]))
while True:
    try:
        (draw,) = pool.take(1)
    except EmptyPoolError:
        break
    print(draw.batch, draw.offset, flush=True)
"""


def test_concurrent_processes_never_share_a_bit(tmp_path: Path) -> None:
    filled(tmp_path, 150, 150)
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", WORKER, str(tmp_path)], stdout=subprocess.PIPE, text=True
        )
        for _ in range(6)
    ]
    taken = [line for w in workers for line in w.communicate()[0].splitlines()]
    assert all(w.returncode == 0 for w in workers)
    assert len(taken) == 300
    assert len(set(taken)) == 300, "a bit was handed out twice"
    assert sum(1 for w in workers if w.returncode == 0) == 6


def test_the_spent_record_is_replaced_whole(tmp_path: Path) -> None:
    pool = filled(tmp_path, 4)
    pool.take(3)
    assert json.loads((tmp_path / "spent.json").read_text()) == {pool.status()[0].batch: 3}
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda p: p.add([], {}, label="x"), "at least one bit"),
        (lambda p: p.add([1], {}, label="../escape"), "label"),
        (lambda p: p.add([1], {}, label="abc\n"), "label"),
        (lambda p: p.take(0), "at least one"),
    ],
)
def test_bad_requests_are_refused(tmp_path: Path, call, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call(Pool(tmp_path))


def test_the_pool_lives_where_the_environment_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(POOL_ENV, str(tmp_path / "custom"))
    assert default_path() == tmp_path / "custom"
    monkeypatch.delenv(POOL_ENV)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert default_path() == tmp_path / "data" / "fairest-coin" / "pool"


def test_the_same_run_cannot_be_pooled_twice(tmp_path: Path) -> None:
    pool = Pool(tmp_path)
    pool.add([1, 0], {"run": "2026-11-02-abc"}, label="abc")
    with pytest.raises(ValueError, match="already pooled"):
        pool.add([0, 1], {"run": "2026-11-02-abc"}, label="abc")


def test_batches_added_in_the_same_second_come_out_oldest_first(tmp_path: Path) -> None:
    pool = Pool(tmp_path)
    pool.add([1], {}, label="zzz")
    pool.add([0], {}, label="aaa")
    assert [d.batch.endswith("zzz") for d in pool.take(2)] == [True, False]


@pytest.mark.parametrize("suffix", [".json", ".bits"])
def test_a_crash_while_adding_leaves_a_working_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    real = coin.pool._write_atomic

    def crash_on_bits(path: Path, data: bytes) -> None:
        if path.suffix == suffix:
            raise OSError("power cut")
        real(path, data)

    monkeypatch.setattr(coin.pool, "_write_atomic", crash_on_bits)
    pool = Pool(tmp_path)
    with pytest.raises(OSError, match="power cut"):
        pool.add([1, 0, 1], {}, label="a")
    monkeypatch.undo()
    assert pool.status() == []
    pool.add([1, 1], {}, label="b")
    assert [len(d.bits) for d in pool.take(2)] == [2]


def test_a_failed_write_never_leaves_a_half_written_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pool = filled(tmp_path, 10)
    pool.take(3)
    before = (tmp_path / "spent.json").read_bytes()

    def fail(descriptor: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(coin.pool, "_sync", fail)
    with pytest.raises(OSError, match="disk full"):
        pool.take(2)
    monkeypatch.undo()
    assert (tmp_path / "spent.json").read_bytes() == before
    assert pool.take(1)[0].offset == 3


def test_a_truncated_batch_spends_nothing(tmp_path: Path) -> None:
    pool = filled(tmp_path, 16)
    (batch,) = pool.status()
    (tmp_path / f"{batch.batch}.bits").write_bytes(b"\x00")  # 8 bits where 16 are recorded
    with pytest.raises(ValueError, match="holds 8 bits"):
        pool.take(12)
    assert pool.status()[0].spent == 0


def test_taking_from_a_pool_that_does_not_exist_creates_nothing(tmp_path: Path) -> None:
    with pytest.raises(EmptyPoolError):
        Pool(tmp_path / "never").take(1)
    assert not (tmp_path / "never").exists()
