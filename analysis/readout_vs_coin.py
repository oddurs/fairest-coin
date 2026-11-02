"""Spike 0069: why did the chip-map prediction miss?

Three back-to-back jobs on every qubit: prepare |0⟩ and read, prepare |1⟩ and read, flip the
coin. The first two measure each qubit's readout as a job actually saw it. Then:

1. How well did the published readout numbers describe that readout?
2. With the measured readout in place of the published one, does a readout-only model
   predict the coin?
3. What is left once the measured readout is undone (the coin's bias before measurement),
   and does a coherent sx error of the size the calibration allows cover it?

    uv run python analysis/readout_vs_coin.py \\
        data/runs/<prepare 0> data/runs/<prepare 1> data/runs/<chip map>
"""

import math
import statistics
import sys

from coin.archive import load_run
from coin.chipmap import tails_by_qubit
from coin.noise import coherent_bias_bound, model_from_calibration
from coin.readout import measured, published_readout


def main(zero_dir: str, one_dir: str, coin_dir: str) -> None:
    zero, one, coin = load_run(zero_dir), load_run(one_dir), load_run(coin_dir)
    readout = measured(zero, one)
    pub0, _ = published_readout(zero.calibration, 0)
    pub1, _ = published_readout(one.calibration, 1)
    gap = (coin.submitted_at - zero.submitted_at).total_seconds()
    print(f"jobs: readout {zero.job_id}, {one.job_id}; coin {coin.job_id}; {gap:.0f} s apart")

    print("\n1. published readout against measured")
    for name, pub, got, shots in (
        ("p(1|0)", pub0, {q: r.p1_given_0 for q, r in readout.items()}, zero.shots),
        ("p(0|1)", pub1, {q: r.p0_given_1 for q, r in readout.items()}, one.shots),
    ):
        qs = sorted(set(pub) & set(got))
        diff = [got[q] - pub[q] for q in qs]
        r = statistics.correlation([pub[q] for q in qs], [got[q] for q in qs])
        print(
            f"   {name}: median published {statistics.median(pub[q] for q in qs):.2%}, "
            f"measured {statistics.median(got[q] for q in qs):.2%}; correlation {r:+.2f}; "
            f"median |difference| {statistics.median(abs(d) for d in diff):.2%} "
            f"({shots:,} shots, 1σ ≈ {math.sqrt(0.01 * 0.99 / shots):.2%} at 1%)"  # noqa: RUF001
        )
    for q in (34, 48, 59, 118):
        r = readout[q]
        print(
            f"   qubit {q}: published p(1|0) {pub0.get(q, math.nan):.3f} p(0|1) "
            f"{pub1.get(q, math.nan):.3f}; measured {r.p1_given_0:.3f} {r.p0_given_1:.3f}"
        )

    tails = tails_by_qubit(coin)
    n = coin.shots
    model = model_from_calibration(coin.calibration)
    rows = []
    for q, r in readout.items():
        t = tails[q] / n
        contrast = 1 - r.p1_given_0 - r.p0_given_1
        # Readout-only prediction from the measured readout, and its σ: the coin's shot noise
        # plus the readout estimates' own.
        predicted = 0.5 * (1 - r.p0_given_1) + 0.5 * r.p1_given_0
        var = (
            t * (1 - t) / n
            + 0.25 * r.p1_given_0 * (1 - r.p1_given_0) / zero.shots
            + 0.25 * r.p0_given_1 * (1 - r.p0_given_1) / one.shots
        )
        sigma = math.sqrt(var)
        before = (t - r.p1_given_0) / contrast if contrast > 0.05 else math.nan
        bound = (
            coherent_bias_bound(model.qubits[q].gates["sx"].error)
            if q in model.qubits
            else math.nan
        )
        rows.append(
            (
                q,
                t,
                predicted,
                sigma,
                before,
                sigma / contrast if contrast > 0.05 else math.nan,
                bound,
            )
        )

    print("\n2. readout-only model with the measured readout")
    within = sum(abs(t - p) <= 3 * s for _, t, p, s, *_ in rows)
    print(f"   {within} of {len(rows)} qubits' coins within 3σ of it")  # noqa: RUF001 - σ is the display text
    residual = [t - p for _, t, p, *_ in rows]
    print(
        f"   coin minus readout-only prediction: median {statistics.median(residual):+.2%}, "
        f"median |·| {statistics.median(abs(x) for x in residual):.2%}"
    )

    print("\n3. the coin before measurement (measured readout undone)")
    usable = [row for row in rows if not math.isnan(row[4])]
    bias = [row[4] - 0.5 for row in usable]
    print(
        f"   {len(usable)} qubits with readout contrast above 0.05: bias before measurement "
        f"median {statistics.median(bias):+.2%}, "
        f"median |·| {statistics.median(abs(b) for b in bias):.2%}"
    )
    fair = sum(abs(row[4] - 0.5) <= 3 * row[5] for row in usable)
    print(f"   fair within 3σ before measurement: {fair} of {len(usable)}")  # noqa: RUF001 - σ is the display text
    bounded = [row for row in usable if not math.isnan(row[6])]
    covered = sum(abs(row[4] - 0.5) <= row[6] + 3 * row[5] for row in bounded)
    print(
        f"   within the coherent sx bound + 3σ: {covered} of {len(bounded)} "  # noqa: RUF001 - σ is the display text
        f"(median bound ±{statistics.median(row[6] for row in bounded):.2%})"
    )
    worst = sorted(usable, key=lambda row: -abs(row[4] - 0.5))[:6]
    print("   largest biases before measurement:")
    for q, t, _, _, before, s, bound in worst:
        print(
            f"     qubit {q}: coin read {t:.4f}, before measurement {before:.4f} ± {s:.4f}, "
            f"coherent bound ±{bound:.4f}"
        )


if __name__ == "__main__":
    main(*sys.argv[1:4])
