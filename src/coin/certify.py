"""Bits a Bell violation vouches for, chosen by the coin's own bits, and what they cost.

The CHSH test's settings must not come from a generator the certificate then vouches for, or
the argument is circular. Here they come from the entropy pool: two bits a round, one for
each side, so the coin's own bits choose how the next coins are read.

A run whose lower bound S_low exceeds 2 vouches for min-entropy in its outcomes. For a
round of the CHSH game, Pironio et al. (Nature 464, 2010) bound the min-entropy of the two
outcome bits, given the settings, by 1 − log₂(1 + √(2 − S²/4)): 0.27 bits at S = 2.5,
0.49 at 2.7, 1 at Tsirelson's 2√2. Taken at S_low, with ε its own failure probability,
that is the rate the run's outcome bits are hashed at, never more.

This does not expand randomness: every round spends two setting bits and certifies under
one. What it buys is a different kind of bit, one whose randomness rests on a measured
violation rather than on trusting the hardware's noise. The bound assumes the rounds are
independent and alike, and that the settings were unknown to the devices; spikes 0028 and
0069 found the chip does not always behave alike, and the settings are in the job before it
runs. Chapter 5 says what that leaves.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from coin import chsh
from coin.archive import EXTRACTION, load_run
from coin.extract import Extraction, seed_bits, toeplitz_extract
from coin.pool import Pool

# Each round's setting pair, from two pool bits: Alice's bit, then Bob's.
BITS_PER_ROUND = 2


def certified_rate(s_low: float) -> float:
    """The min-entropy of a round's two outcome bits that a CHSH value of `s_low` certifies.

    Pironio et al.'s bound, 1 − log₂(1 + √(2 − S²/4)); 0 when S ≤ 2, where no local model
    is ruled out, and at most 1, its value at 2√2.
    """
    if s_low <= chsh.CLASSICAL_BOUND:
        return 0.0
    s = min(s_low, chsh.TSIRELSON)
    return 1 - math.log2(1 + math.sqrt(max(0.0, 2 - s * s / 4)))


def settings_from_pool(pool: Pool, rounds: int) -> tuple[tuple[int, ...], list[dict[str, Any]]]:
    """Each round's setting, `chsh.SETTINGS[2a + b]` for pool bits a then b, and where the
    bits came from: each batch drawn on, from which offset, how many. The bits are spent."""
    draws = pool.take(BITS_PER_ROUND * rounds)
    bits = np.concatenate([draw.bits for draw in draws])
    choices = tuple(int(2 * bits[2 * i] + bits[2 * i + 1]) for i in range(rounds))
    sources = [
        {"batch": draw.batch, "offset": draw.offset, "bits": len(draw.bits)} for draw in draws
    ]
    return choices, sources


@dataclass(frozen=True)
class Certification:
    run_dir: Path
    s: float
    s_low: float
    epsilon: float
    rate_per_round: float  # certified min-entropy of a round's two outcome bits
    setting_bits: int  # spent choosing the settings
    batch: str | None  # the certified batch added to the pool, if any
    extraction: Extraction | None

    @property
    def certified_bits(self) -> int:
        return 0 if self.extraction is None else len(self.extraction.bits)

    @property
    def net(self) -> int:
        """Certified bits out less setting bits in: negative, as it must be."""
        return self.certified_bits - self.setting_bits


def certify(run_dir: Path, pool: Pool) -> Certification:
    """Hash a CHSH run's outcome bits at the rate its S_low certifies, into the pool.

    Only a run whose settings came from the pool qualifies, and only before it is
    published (its shots and seed would make the bits predictable). A run whose S_low does
    not exceed 2 certifies nothing and adds nothing.
    """
    run = load_run(run_dir)
    values = run.prediction.values if run.prediction else {}
    if values.get("purpose") != "chsh":
        raise ValueError(f"{run_dir} is not a CHSH run")
    if not values.get("settings_source", {}).get("pool"):
        raise ValueError(
            f"{run_dir}'s settings did not come from the pool, so its certificate would rest "
            "on whatever chose them"
        )
    if (run_dir / EXTRACTION).exists():
        raise ValueError(f"{run_dir} is already published; its bits are no longer secret")
    if run.memory is None or "choices" not in run.extra:
        raise ValueError(f"{run_dir} kept no per-shot memory and choices")
    result = chsh.estimate(chsh.counts_by_setting(run.memory, run.extra["choices"]))
    epsilon = values["epsilon"]
    s_low = result.lower_bound(epsilon)
    rate = certified_rate(s_low)
    setting_bits = BITS_PER_ROUND * result.rounds
    if rate == 0:
        return Certification(run_dir, result.s, s_low, epsilon, 0.0, setting_bits, None, None)
    # Two outcome bits a round, Alice's then Bob's; the round's min-entropy spreads over both.
    outcomes = np.array(
        [int(bit) for outcome in run.memory for bit in (outcome[1], outcome[0])], dtype=np.uint8
    )
    seed = seed_bits(2 * len(outcomes))
    extraction = toeplitz_extract(outcomes, seed, entropy_per_bit=rate / BITS_PER_ROUND)
    provenance = {
        "run": run_dir.name,
        "job_id": run.job_id,
        "backend": run.backend,
        "qubits": list(run.qubits),
        "certified": True,
        "s": result.s,
        "s_low": s_low,
        "s_epsilon": epsilon,
        "rate_per_round": rate,
        "settings_source": values["settings_source"],
        "entropy_per_bit": extraction.entropy_per_bit,
        "epsilon": extraction.epsilon,
        "input_bits": extraction.input_bits,
        "seed": np.packbits(seed[: extraction.seed_used]).tobytes().hex(),
        "seed_bits": extraction.seed_used,
    }
    batch = pool.add(extraction.bits, provenance, label=run.job_id)
    return Certification(run_dir, result.s, s_low, epsilon, rate, setting_bits, batch, extraction)


def report(certification: Certification) -> str:
    c = certification
    lines = [
        f"S            {c.s:.3f}; S_low {c.s_low:.3f} at ε = {c.epsilon:.1e}",
        f"certified    {c.rate_per_round:.3f} bits of min-entropy per round",
        f"settings     {c.setting_bits:,} pool bits spent choosing them",
        f"produced     {c.certified_bits:,} certified bits"
        + (f" in batch {c.batch}" if c.batch else ": S_low does not exceed 2, nothing credited"),
        f"net          {c.net:+,} bits: the loop spends more randomness than it certifies, "
        "so it does not expand it",
    ]
    return "\n".join(lines)
