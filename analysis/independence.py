"""Spike 0028: are the hardware bits independent?

Reads an archived run's per-shot memory and asks three questions, each against what
independent coins would give:

1. Memory: does a qubit's outcome depend on its own earlier outcomes? Autocorrelation at
   lags 1-100, raw and within 5,000-shot blocks (which removes drift slower than ~1 s), with
   a Ljung-Box test per qubit.
2. Crosstalk: are two qubits' outcomes in the same shot correlated? Every coupled pair,
   with every uncoupled pair as the control.
3. Consequence: does von Neumann's extractor, applied to each qubit's own shots, give fair
   bits? This is what chapter 3 needs, measured directly.

    uv run python analysis/independence.py data/runs/2026-11-02-dbjuh5d6p51s73cljo60

Assumes the memory is in the order the shots ran, which IBM's sampler returns; the drift
this run shows across its halves (chipmap._drift) would vanish if it were not.
"""

import itertools
import math
import sys

import numpy as np
import numpy.typing as npt

from coin import extract
from coin.archive import Run, load_run

MAX_LAG = 100
BLOCK = 5_000  # shots; at the default 250 µs repetition delay, 1.25 s
# Bonferroni: a family of tests at 5% overall.
FAMILY_ALPHA = 0.05
SIGMA = "\N{GREEK SMALL LETTER SIGMA}"
TIMES = "\N{MULTIPLICATION SIGN}"

Bits = npt.NDArray[np.bool_]
Floats = npt.NDArray[np.float64]


def bits(run: Run) -> Bits:
    """The run's memory as shots × classical bits, column i being classical bit i."""
    if run.memory is None:
        raise ValueError(f"job {run.job_id} kept no per-shot memory")
    width = len(run.memory[0])
    raw = np.frombuffer("".join(run.memory).encode(), dtype=np.uint8).reshape(-1, width)
    return (raw == ord("1"))[:, ::-1]


def centred(x: Bits, block: int | None) -> Floats:
    """Each column minus its mean: over the whole run, or within each block of shots."""
    f = x.astype(np.float64)
    if block is None:
        return f - f.mean(axis=0)
    out = np.empty_like(f)
    for start in range(0, len(f), block):
        chunk = f[start : start + block]
        out[start : start + block] = chunk - chunk.mean(axis=0)
    return out


def autocorrelation(xc: Floats, max_lag: int = MAX_LAG) -> Floats:
    """r_k for k = 1..max_lag, per column: lags × columns."""
    variance = np.einsum("ij,ij->j", xc, xc)
    return np.array(
        [np.einsum("ij,ij->j", xc[:-k], xc[k:]) / variance for k in range(1, max_lag + 1)]
    )


def ljung_box(r: Floats, n: int) -> Floats:
    """Q = n(n+2)·Σ r_k²/(n−k) per column; χ² with max_lag degrees of freedom if independent."""
    k = np.arange(1, len(r) + 1)[:, None]
    return n * (n + 2) * np.sum(r**2 / (n - k), axis=0)


def chi2_sf(q: float, df: int) -> float:
    """P(χ²_df > q), by the Wilson-Hilferty cube-root normal approximation.

    Good to a few percent relative for df = 100 well into the tail, which is all a
    Bonferroni threshold needs; it keeps the analysis to numpy and the standard library.
    """
    scale = 2 / (9 * df)
    z = ((q / df) ** (1 / 3) - (1 - scale)) / math.sqrt(scale)
    return 0.5 * math.erfc(z / math.sqrt(2))


def normal_two_sided(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2))


def pair_correlation(xc: Floats, pairs: list[tuple[int, int]]) -> Floats:
    """Pearson r between the columns of each pair, from centred data."""
    norm = np.sqrt(np.einsum("ij,ij->j", xc, xc))
    return np.array([float(xc[:, a] @ xc[:, b]) / (norm[a] * norm[b]) for a, b in pairs])


def von_neumann(x: Bits) -> tuple[Floats, Floats]:
    """Per column: the fraction of von Neumann output bits that are 1, and how many there are.

    Uses the library's extractor, so this judges the code chapter 3 runs.
    """
    outputs = [extract.von_neumann(x[:, c]) for c in range(x.shape[1])]
    count = np.array([len(o) for o in outputs], dtype=np.float64)
    return np.array([o.mean() for o in outputs]), count


def coupling(run: Run) -> set[tuple[int, int]]:
    return {
        (min(g["qubits"]), max(g["qubits"]))
        for g in run.calibration.get("gates", [])
        if len(g["qubits"]) == 2
    }


def von_neumann_lag1(x: Bits) -> tuple[Floats, Floats]:
    """Per column: the lag-1 autocorrelation of the von Neumann output bits, and their count.

    Fair output is not enough for chapter 3: the output bits must not predict each other.
    """
    r, m = [], []
    for c in range(x.shape[1]):
        out = extract.von_neumann(x[:, c]).astype(np.float64)
        out -= out.mean()
        r.append(float(out[:-1] @ out[1:]) / float(out @ out))
        m.append(len(out))
    return np.array(r), np.array(m, dtype=np.float64)


def spectral_peak(column: Bits) -> tuple[float, float, float]:
    """The strongest periodic component of one qubit's shots.

    Returns its frequency in cycles per shot, its power over the mean power, and the
    probability that white noise would give a peak that strong anywhere in the spectrum
    (periodogram ordinates of independent bits are exponential, so P(max > t) ≈ N·e^(−t)).
    A disturbance at a fixed frequency shows as one sharp line; slow switching as power
    piled at the lowest frequencies.
    """
    c = column.astype(np.float64)
    c -= c.mean()
    power = np.abs(np.fft.rfft(c)) ** 2
    power[0] = 0.0
    peak = int(np.argmax(power))
    ratio = float(power[peak] / power[1:].mean())
    return peak / len(c), ratio, min(1.0, (len(power) - 1) * math.exp(-ratio))


def _p(p: float) -> str:
    return "<1e-300" if p == 0 else f"{p:.0e}"


def main(run_dir: str) -> None:
    run = load_run(run_dir)
    x = bits(run)
    n, width = x.shape
    qubit = run.qubits
    print(f"run {run.job_id}: {run.backend}, {width} qubit(s) {TIMES} {n:,} shots")
    varying = [c for c in range(width) if 0 < x[:, c].mean() < 1]
    threshold = FAMILY_ALPHA / len(varying)

    print(f"\n1. memory: autocorrelation at lags 1-{MAX_LAG}")
    for label, block in (("whole run", None), (f"within {BLOCK:,}-shot blocks", BLOCK)):
        r = autocorrelation(centred(x[:, varying], block))
        z = r * math.sqrt(n)
        p = np.array([chi2_sf(float(v), MAX_LAG) for v in ljung_box(r, n)])
        # Ljung-Box spreads a one-lag signal over all the lags; lag 1, the shot just before,
        # is where reset or readout memory would show, so it gets its own test.
        lag1_p = np.array([normal_two_sided(float(v)) for v in z[0]])
        flagged = [i for i in np.argsort(p) if p[i] < threshold or lag1_p[i] < threshold]
        rest = [i for i in range(len(varying)) if i not in flagged]
        print(f"   {label}:")
        print(
            f"     flagged (Ljung-Box or lag 1, 5% Bonferroni over {len(varying)} qubits): "
            + (
                ", ".join(
                    f"{qubit[varying[i]]} (Q p={_p(float(p[i]))}, lag 1 {z[0, i]:+.1f}{SIGMA})"
                    for i in flagged
                )
                or "none"
            )
        )
        if rest:
            zr = z[:, rest]
            print(
                f"     the other {len(rest)}: spread of r_k·√n {np.std(zr):.3f} (1 if "
                f"independent); |z| > 4 on {int(np.sum(np.abs(zr) > 4))} of {zr.size:,} "
                f"(qubit, lag) pairs, expected {zr.size * normal_two_sided(4):.1f}; lag 1 "
                f"|z| > 3 on {int(np.sum(np.abs(zr[0]) > 3))}, expected "
                f"{len(rest) * normal_two_sided(3):.1f}"
            )
        if block is not None:
            lags = (1, 2, 3, 5, 10, 20, 50, 100)
            for i in flagged:
                frequency, ratio, chance = spectral_peak(x[:, varying[i]])
                print(
                    f"     qubit {qubit[varying[i]]} r_k at k = {', '.join(map(str, lags))}: "
                    + " ".join(f"{r[k - 1, i]:+.4f}" for k in lags)
                    + f"; strongest line {frequency:.5f} cycles/shot, {ratio:.0f}{TIMES} mean power"
                    f" (white noise: p={_p(chance)})"
                )

    if width > 1:
        print("\n2. crosstalk: correlation between qubits in the same shot")
        index = {q: c for c, q in enumerate(qubit)}
        edges = sorted(
            (index[a], index[b])
            for a, b in coupling(run)
            if a in index and b in index and index[a] in varying and index[b] in varying
        )
        adjacent = set(edges)
        others = [pair for pair in itertools.combinations(varying, 2) if pair not in adjacent]
        for label, block in (("whole run", None), (f"within {BLOCK:,}-shot blocks", BLOCK)):
            xc = centred(x, block)
            print(f"   {label}:")
            for name, pairs in (("coupled", edges), ("uncoupled", others)):
                z = pair_correlation(xc, pairs) * math.sqrt(n)
                cut = FAMILY_ALPHA / len(pairs)
                past = [i for i in np.argsort(-np.abs(z)) if normal_two_sided(float(z[i])) < cut]
                clean = np.delete(z, past)
                print(
                    f"     {name} pairs: {len(pairs):,}; past 5% Bonferroni: {len(past)}"
                    + (
                        ""
                        if not past
                        else " ("
                        + ", ".join(
                            f"{qubit[pairs[i][0]]}-{qubit[pairs[i][1]]} {z[i]:+.1f}{SIGMA}"
                            for i in past[:8]
                        )
                        + (", …" if len(past) > 8 else "")
                        + ")"
                    )
                    + f"; the rest: spread of r·√n {np.std(clean):.3f}, |z| > 3 on "
                    f"{int(np.sum(np.abs(clean) > 3))}, expected "
                    f"{len(clean) * normal_two_sided(3):.1f}"
                )

    print("\n3. consequence: von Neumann on each qubit's own shots")
    fraction, count = von_neumann(x[:, varying])
    z = (fraction - 0.5) * 2 * np.sqrt(count)
    worst = int(np.argmax(np.abs(z)))
    print(
        f"   output bits per qubit: median {int(np.median(count)):,}; fairness |z| > 3 on "
        f"{int(np.sum(np.abs(z) > 3))} of {len(z)}, expected {len(z) * normal_two_sided(3):.1f};"
        f" spread {np.std(z):.3f} (1 if fair); past 5% Bonferroni: "
        f"{sum(normal_two_sided(float(v)) < threshold for v in z)}"
    )
    print(
        f"   least fair: qubit {qubit[varying[worst]]}, {fraction[worst]:.4f} ones "
        f"({z[worst]:+.1f}{SIGMA}) from {int(count[worst]):,} output bits"
    )
    r1, m = von_neumann_lag1(x[:, varying])
    z1 = r1 * np.sqrt(m)
    past = [i for i in np.argsort(-np.abs(z1)) if normal_two_sided(float(z1[i])) < threshold]
    print(
        f"   output lag-1 correlation: |z| > 3 on {int(np.sum(np.abs(z1) > 3))}, expected "
        f"{len(z1) * normal_two_sided(3):.1f}; spread {np.std(z1):.3f}; past 5% Bonferroni: "
        + (", ".join(f"{qubit[varying[i]]} ({z1[i]:+.1f}{SIGMA})" for i in past) or "none")
    )


if __name__ == "__main__":
    main(sys.argv[1])
