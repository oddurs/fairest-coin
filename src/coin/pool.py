"""The entropy pool: hardware bits harvested in batches, spent one at a time, never twice.

A job per flip would spend the monthly QPU allowance in an afternoon, so `coin harvest`
runs one job, extracts near-uniform bits from it, and adds them here as a batch with its
provenance. `coin flip` then spends them.

Every bit is spent at most once, across processes too. Spending holds an exclusive lock on
the pool, records the new spent count durably (written to a temporary file, flushed, and
renamed over the old one), and only then hands the bits out. A crash between the record and
the hand-out loses those bits; it never reuses them.

Layout, in one directory:

    <batch>.bits   the batch's bits, packed eight to a byte
    <batch>.json   its provenance: the run, the qubit, the extraction and the seed
    spent.json     how many bits of each batch have been spent
    lock           held while reading or changing spent.json

What it does not protect against:

- Someone who reads a batch's raw shots. Toeplitz hashing lets the seed be public only
  while the source is secret: the archived run plus the recorded seed determine every bit.
  Commit a harvest's run to a public archive only once its batch is spent; after that, it
  lets anyone check every flip it gave.
- Deleting spent.json, which makes every bit unspent again.
- A pool directory shared over a network filesystem: flock may lock only on one host.
"""

import fcntl
import json
import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from coin import durable
from coin.extract import Bits, as_bits

POOL_ENV = "COIN_POOL"
# Named by the UTC time to the microsecond, so name order is age order.
_BATCH = re.compile(r"[0-9]{8}T[0-9]{12}-[A-Za-z0-9_-]+")


class EmptyPoolError(Exception):
    """The pool has fewer unspent bits than were asked for."""


@dataclass(frozen=True)
class Draw:
    """Bits taken from the pool, and exactly where they came from."""

    bits: Bits
    batch: str
    offset: int  # the position of the first bit within its batch
    provenance: dict[str, Any]


@dataclass(frozen=True)
class BatchStatus:
    batch: str
    total: int
    spent: int
    provenance: dict[str, Any]

    @property
    def remaining(self) -> int:
        return self.total - self.spent


def default_path() -> Path:
    """$COIN_POOL, else $XDG_DATA_HOME/fairest-coin/pool, else ~/.local/share/fairest-coin/pool."""
    if path := os.environ.get(POOL_ENV):
        return Path(path)
    data = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(data) / "fairest-coin" / "pool"


class Pool:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else default_path()

    def add(self, bits: npt.ArrayLike, provenance: dict[str, Any], label: str) -> str:
        """Add a batch and return its name, `<UTC time>-<label>`, such as a job id."""
        x = as_bits(bits)
        if len(x) == 0:
            raise ValueError("a batch needs at least one bit")
        batch = f"{datetime.now(UTC):%Y%m%dT%H%M%S%f}-{label}"
        if not _BATCH.fullmatch(batch):
            raise ValueError(f"label must be letters, digits, - or _, got {label!r}")
        durable.make_directory(self.path)
        record = {**provenance, "bits": len(x), "added_at": datetime.now(UTC).isoformat()}
        with self._locked():
            if (self.path / f"{batch}.bits").exists():
                raise ValueError(f"batch {batch} already exists")
            # The same shots extracted twice, even with fresh seeds, are not twice the
            # entropy: the second batch would be spending the first one's margin.
            # Keyed on the job, not the directory: a copied or renamed run is the same shots.
            # A provenance with no job id falls back to the run's name.
            job, run = provenance.get("job_id"), provenance.get("run")
            for name, existing in self._provenances().items():
                if job is not None and existing.get("job_id") == job:
                    raise ValueError(f"job {job} is already pooled, as batch {name}")
                if job is None and run is not None and existing.get("run") == run:
                    raise ValueError(f"run {run} is already pooled, as batch {name}")
            # Bits and provenance first, both atomically; a batch exists once its .bits does.
            durable.replace(self.path / f"{batch}.json", json.dumps(record, indent=2).encode())
            durable.replace(self.path / f"{batch}.bits", np.packbits(x).tobytes())
        return batch

    def take(self, n: int) -> list[Draw]:
        """Spend the next n bits, oldest batch first; EmptyPoolError if there are too few."""
        if n < 1:
            raise ValueError(f"take at least one bit, got {n}")
        if not self.path.exists():
            raise EmptyPoolError(f"the pool has 0 unspent bit(s), {n} needed; run `coin harvest`")
        with self._locked():
            spent = self._spent()
            provenance = self._provenances()
            available = sum(int(p["bits"]) - spent.get(b, 0) for b, p in provenance.items())
            if available < n:
                raise EmptyPoolError(
                    f"the pool has {available} unspent bit(s), {n} needed; run `coin harvest`"
                )
            draws: list[tuple[str, int, int]] = []
            needed = n
            for batch, record in provenance.items():
                start = spent.get(batch, 0)
                count = min(needed, int(record["bits"]) - start)
                if count > 0:
                    draws.append((batch, start, count))
                    spent[batch] = start + count
                    needed -= count
                if needed == 0:
                    break
            # Read before recording, so a damaged batch spends nothing.
            result = [
                Draw(
                    self._bits(batch, int(provenance[batch]["bits"]))[start : start + count],
                    batch,
                    start,
                    provenance[batch],
                )
                for batch, start, count in draws
            ]
            # Recorded as spent before anything is returned.
            durable.replace(self.path / "spent.json", json.dumps(spent, indent=2).encode())
        return result

    def status(self) -> list[BatchStatus]:
        """Every batch, oldest first, with how much of it is spent."""
        if not self.path.exists():
            return []
        with self._locked():
            spent = self._spent()
            return [
                BatchStatus(batch, int(record["bits"]), spent.get(batch, 0), record)
                for batch, record in self._provenances().items()
            ]

    def require_writable(self) -> None:
        """Raise OSError now if bits could not be added, before anything costs QPU time."""
        with self._locked():
            probe = self.path / ".writable"
            probe.write_bytes(b"")
            probe.unlink()

    @contextmanager
    def _locked(self) -> Generator[None]:
        durable.make_directory(self.path)
        with (self.path / "lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _provenances(self) -> dict[str, dict[str, Any]]:
        """Every complete batch, oldest first, with its provenance, read once."""
        # A batch exists once its .bits does; add() writes the .json first, so a crash in
        # between leaves only a .json, which is ignored.
        return {
            p.stem: json.loads((self.path / f"{p.stem}.json").read_text())
            for p in sorted(self.path.glob("*.bits"))
            if _BATCH.fullmatch(p.stem)
        }

    def _spent(self) -> dict[str, int]:
        path = self.path / "spent.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def _bits(self, batch: str, n: int) -> Bits:
        packed = np.frombuffer((self.path / f"{batch}.bits").read_bytes(), dtype=np.uint8)
        bits = np.unpackbits(packed)[:n]
        if len(bits) != n:
            raise ValueError(f"batch {batch} holds {len(bits)} bits, but records {n}")
        return bits


def receipt(draw: Draw, flipped_at: datetime) -> dict[str, Any]:
    """Where one flip came from, for `coin flip`: the run, the qubit, the extraction.

    The fields are documented in docs/receipt.schema.json. With the archived run, `run`
    and the batch's recorded seed recompute the bit.
    """
    if len(draw.bits) != 1:
        raise ValueError(f"a receipt is for one flip, got {len(draw.bits)} bits")
    bit = int(draw.bits[0])
    p = draw.provenance
    return {
        "outcome": "TAILS" if bit else "HEADS",
        "bit": bit,
        "flipped_at": flipped_at.isoformat(),
        "backend": p.get("backend"),
        "qubit": p.get("qubit"),
        "job_id": p.get("job_id"),
        "run": p.get("run"),
        "harvested_at": p.get("added_at"),
        "batch": draw.batch,
        "offset": draw.offset,
        "batch_bits": p.get("bits"),
        "extractor": "toeplitz",
        "entropy_per_bit": p.get("entropy_per_bit"),
        "epsilon": p.get("epsilon"),
    }
