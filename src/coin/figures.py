"""Every figure in `docs/figures/`, rendered from the archived runs and nothing else.

A figure that cannot be regenerated is a claim, not evidence. Each figure here is a
function of `data/runs/`, written as SVG whose bytes depend only on the archive and the
locked matplotlib, so `--check` can prove that the committed figures are the ones the
archive gives.

matplotlib lives in the optional `figures` dependency group; `import coin` never loads it.
"""

import argparse
import math
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import numpy.typing as npt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.figure import Figure
from matplotlib.typing import RcKeyType

from coin import chsh
from coin.archive import load_run
from coin.battery import ALPHA, battery
from coin.chipmap import compare, tails_by_qubit
from coin.extract import toeplitz_extract, von_neumann

# Relative to the repository root, where scripts/figures runs from.
RUNS = Path("data/runs")
FIGURES_DIR = Path("docs/figures")

FIRST_RUN = "2026-11-01-dbjsk29ffo6c73baaosg"
CHIP_MAP_RUN = "2026-11-02-dbjuh5d6p51s73cljo60"
# The CHSH test predicted, committed in c86a39c, then run (0042).
CHSH_RUN = "2026-11-05-dbmfqed8ft8s738upl80"

# One grey for text, axes and neutral marks: about 4.3:1 against both GitHub's white
# and its dark #0d1117, because one SVG has to read on either background.
INK = "#7a7a7a"
# Mid-luminance, checked for colour-blind separation and 3:1 contrast on both themes.
MEASURED = "#3a80dc"
PREDICTED = "#e2622d"
# The chip map's diverging scale: heads-heavy blue, fair grey, tails-heavy orange. The
# middle is INK so a fair qubit reads as neutral on either background.
BIAS = LinearSegmentedColormap.from_list("bias", [MEASURED, INK, PREDICTED])
# Most qubits sit within a few percentage points of fair; a few sit tens away. Clipping the
# colour scale here keeps the many visible, and the few are named in the caption instead.
BIAS_CLIP = 0.05
SIGMA = "\N{GREEK SMALL LETTER SIGMA}"
MINUS = "\N{MINUS SIGN}"
ALPHA_SIGN = "\N{GREEK SMALL LETTER ALPHA}"
# Beyond this the residual is named on the scatter, not just marked.
NAMED_RESIDUAL = 0.05

STYLE: dict[RcKeyType, Any] = {
    # Text stays text: searchable, small, and free of glyph outlines that vary by renderer.
    "svg.fonttype": "none",
    # Clip-path and marker ids are hashes; a fixed salt makes them the same on every run.
    "svg.hashsalt": "fairest-coin",
    # matplotlib's bundled font, so layout metrics do not depend on the machine's fonts. The
    # viewer draws the text in its own fallback, so margins leave room for a wider face.
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "figure.dpi": 100,
    "savefig.dpi": 100,
    "savefig.transparent": True,
    "text.color": INK,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "axes.titlecolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
}

# No creation date, so rendering twice gives the same bytes.
METADATA = {"Date": None}


def first_coin(runs: Path) -> Figure:
    """The first hardware coin: measured tails fraction against the prediction, with 1σ."""
    run = load_run(runs / FIRST_RUN)
    if run.prediction is None:
        raise ValueError(f"{runs / FIRST_RUN}: the first run is expected to carry a prediction")
    predicted = run.prediction.values
    n = predicted["shots"]
    p_predicted = predicted["p_tails"]
    sigma_predicted = predicted["sigma_tails"] / n

    tails = run.counts.get("1", 0)
    p_measured = tails / run.shots
    # Binomial standard error of a fraction: √(p(1−p)/n).
    sigma_measured = math.sqrt(p_measured * (1 - p_measured) / run.shots)

    fig = Figure(figsize=(7.2, 2.8))
    ax = fig.add_subplot()
    # Values sit in the row labels, clear of the marks and the fair line.
    rows = [
        ("measured", p_measured, sigma_measured, MEASURED),
        ("predicted", p_predicted, sigma_predicted, PREDICTED),
    ]
    for y, (_, p, sigma, colour) in enumerate(rows):
        ax.errorbar(p, y, xerr=sigma, fmt="o", color=colour, markersize=8, capsize=4, lw=2)
    ax.axvline(0.5, color=INK, ls="--", lw=1, zorder=0)
    ax.annotate(
        "fair, 0.5",
        (0.5, 1),
        xycoords=("data", "axes fraction"),
        xytext=(4, -4),
        textcoords="offset points",
        va="top",
        fontsize=9,
    )

    ax.set_yticks(
        range(len(rows)), [f"{label}\n{p:.4f} ± {sigma:.4f}" for label, p, sigma, _ in rows]
    )
    for label in ax.get_yticklabels():
        label.set_multialignment("right")
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(0.47, 0.53)
    ax.set_xlabel("fraction of shots that came up tails (error bars 1\N{GREEK SMALL LETTER SIGMA})")
    ax.set_title("The first coin on real hardware: measured against predicted", loc="left")
    qubits = ", ".join(str(q) for q in run.qubits)
    fig.text(
        0.01,
        0.02,
        f"{tails} of {run.shots} shots tails · prediction written before submission · "
        f"{run.backend} · qubit {qubits} · job {run.job_id}",
        fontsize=8,
    )
    fig.subplots_adjust(left=0.2, right=0.97, top=0.88, bottom=0.27)
    return fig


def heavy_hex_layout(edges: set[tuple[int, int]]) -> dict[int, tuple[float, float]]:
    """Grid positions for IBM's heavy-hex chips, derived from the coupling graph alone.

    A Heron chip is rows of consecutively numbered qubits joined in a line, with single
    bridge qubits linking each row to the next. Rows go down the page, one row every two
    units; a bridge sits halfway between the rows it joins, in its neighbours' column.
    Raises ValueError for a graph of any other shape rather than drawing it wrong.
    """
    nodes = {q for edge in edges for q in edge}
    in_row = {q for a, b in edges if abs(a - b) == 1 for q in (a, b)}
    rows: list[list[int]] = []
    for q in sorted(in_row):
        if rows and (rows[-1][-1], q) in edges:
            rows[-1].append(q)
        else:
            rows.append([q])
    position: dict[int, tuple[float, float]] = {}
    row_of: dict[int, int] = {}
    for r, row in enumerate(rows):
        for q in row:
            position[q] = (float(q - row[0]), -2.0 * r)
            row_of[q] = r
    for q in sorted(nodes - in_row):
        neighbours = sorted((b if a == q else a) for a, b in edges if q in (a, b))
        if len(neighbours) != 2 or any(n not in row_of for n in neighbours):
            raise ValueError(f"qubit {q} is neither in a row nor a bridge between two rows")
        upper, lower = sorted(neighbours, key=lambda n: row_of[n])
        if row_of[lower] != row_of[upper] + 1 or position[upper][0] != position[lower][0]:
            raise ValueError(f"bridge qubit {q} does not join adjacent rows in one column")
        position[q] = (position[upper][0], position[upper][1] - 1.0)
    return position


def _coupling(calibration: dict[str, Any]) -> set[tuple[int, int]]:
    """Every pair of qubits a two-qubit gate is calibrated on, each pair once."""
    return {
        (min(gate["qubits"]), max(gate["qubits"]))
        for gate in calibration["gates"]
        if len(gate["qubits"]) == 2
    }


def chip_map(runs: Path) -> Figure:
    """Every qubit's measured bias, drawn where it sits on the chip."""
    run = load_run(runs / CHIP_MAP_RUN)
    edges = _coupling(run.calibration)
    position = heavy_hex_layout(edges)
    bias = {q: t / run.shots - 0.5 for q, t in tails_by_qubit(run).items()}

    fig = Figure(figsize=(8.4, 8.2))
    ax = fig.add_subplot()
    for a, b in sorted(edges):
        (xa, ya), (xb, yb) = position[a], position[b]
        ax.plot([xa, xb], [ya, yb], color=INK, lw=1, zorder=0)
    norm = Normalize(-BIAS_CLIP, BIAS_CLIP, clip=True)
    qubits = sorted(bias)
    ax.scatter(
        [position[q][0] for q in qubits],
        [position[q][1] for q in qubits],
        c=[bias[q] for q in qubits],
        cmap=BIAS,
        norm=norm,
        s=230,
        edgecolors="none",
        zorder=1,
    )
    for q in qubits:
        ax.annotate(
            str(q), position[q], ha="center", va="center", fontsize=6, color="white", zorder=2
        )
    ax.set_aspect("equal")
    ax.set_axis_off()

    colorbar = fig.colorbar(
        matplotlib.cm.ScalarMappable(norm=norm, cmap=BIAS),
        ax=ax,
        orientation="horizontal",
        fraction=0.035,
        pad=0.02,
        format=lambda x, _: f"{x:+.0%}",
    )
    colorbar.outline.set_visible(False)
    # matplotlib rasterizes a long colour bar into an embedded PNG, whose zlib bytes differ
    # between platforms; as vector paths it renders identically everywhere.
    assert colorbar.solids is not None, "a ScalarMappable's colour bar is always drawn"
    colorbar.solids.set_rasterized(False)
    colorbar.set_label(f"measured bias, fraction of tails {MINUS} 0.5: heads-heavy ← → tails-heavy")
    beyond = sorted((q for q in qubits if abs(bias[q]) > BIAS_CLIP), key=lambda q: -abs(bias[q]))
    ax.set_title(f"Every qubit of {run.backend} is a coin, and each one leans", loc="left")
    named = [f"{q} ({bias[q]:+.1%})" for q in beyond]
    # Five to a line, so no entry is split across lines.
    lines = [", ".join(named[i : i + 5]) for i in range(0, len(named), 5)]
    fig.text(
        0.02,
        0.015,
        f"beyond the ±{BIAS_CLIP:.0%} colour scale: "
        + ",\n".join(lines)
        + f"\n{run.shots:,} shots per qubit, all {len(qubits)} in one job · job {run.job_id}",
        fontsize=8,
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.13)
    return fig


def prediction_scatter(runs: Path) -> Figure:
    """Each qubit's predicted bias against its measured bias, whole chip and close to fair."""
    run = load_run(runs / CHIP_MAP_RUN)
    results = compare(run)
    far = [r for r in results if abs(r.z) > 3]
    near = [r for r in results if abs(r.z) <= 3]

    fig = Figure(figsize=(8.4, 4.6))
    whole, close = fig.subplots(1, 2)
    for ax in (whole, close):
        for group, style in (
            (near, {"fmt": "o", "color": MEASURED, "label": f"within 3{SIGMA} of its prediction"}),
            (
                far,
                {"fmt": "o", "color": INK, "mfc": "none", "label": f"more than 3{SIGMA} off"},
            ),
        ):
            ax.errorbar(
                [r.predicted - 0.5 for r in group],
                [r.measured - 0.5 for r in group],
                # Binomial standard error of each measured fraction at the run's shot count.
                yerr=[math.sqrt(r.measured * (1 - r.measured) / r.shots) for r in group],
                markersize=4,
                elinewidth=1,
                lw=0,
                **style,
            )
        ax.axhline(0, color=INK, lw=0.5, ls=":", zorder=0)
        ax.axvline(0, color=INK, lw=0.5, ls=":", zorder=0)
        ax.set_xlabel("predicted bias")
    # The whole chip: predictions span far less than the measurements, so each axis gets
    # its own range and the panel is not square.
    pad = 0.02
    x = [r.predicted - 0.5 for r in results]
    y = [r.measured - 0.5 for r in results]
    whole.set_xlim(min(x) - pad, max(x) + pad)
    whole.set_ylim(min(y) - pad, max(y) + pad)
    low, high = min(*x, *y) - pad, max(*x, *y) + pad
    whole.plot([low, high], [low, high], color=PREDICTED, lw=1, zorder=0)
    whole.xaxis.set_major_formatter(lambda v, _: f"{v:+.0%}")
    whole.yaxis.set_major_formatter(lambda v, _: f"{v:+.0%}")
    # Close to fair, where the error bars are visible: square, so the line sits at 45°.
    zoom = 0.02
    close.plot([-zoom, zoom], [-zoom, zoom], color=PREDICTED, lw=1, zorder=0)
    close.set_xlim(-zoom, zoom)
    close.set_ylim(-zoom, zoom)
    close.set_aspect("equal")
    close.xaxis.set_major_formatter(lambda v, _: f"{v:+.1%}")
    close.yaxis.set_major_formatter(lambda v, _: f"{v:+.1%}")
    whole.set_ylabel("measured bias")
    for r in far:
        if abs(r.measured - r.predicted) > NAMED_RESIDUAL:
            whole.annotate(
                str(r.qubit),
                (r.predicted - 0.5, r.measured - 0.5),
                xytext=(4, 2),
                textcoords="offset points",
                fontsize=7,
            )
    whole.set_title("the whole chip", loc="left", fontsize=10)
    close.set_title("close to fair (±2%)", loc="left", fontsize=10)
    whole.legend(loc="lower right", fontsize=8, frameon=False)
    fig.suptitle(
        f"Predicted from calibration, then measured: {len(near)} of {len(results)} qubits "
        f"land within 3{SIGMA}",
        x=0.01,
        ha="left",
        color=INK,
    )
    # compare() has already refused a run without a prediction.
    reasons: dict[str, str] = run.prediction.values["excluded"] if run.prediction else {}
    excluded = ", ".join(sorted(reasons, key=int))
    fig.text(
        0.01,
        0.02,
        f"orange line: measured = predicted · error bars 1{SIGMA} at {run.shots:,} shots · "
        f"named: more than {NAMED_RESIDUAL:.0%} off\nnot predicted (calibration unusable): "
        f"{excluded} · job {run.job_id}",
        fontsize=8,
    )
    fig.subplots_adjust(left=0.09, right=0.98, top=0.86, bottom=0.2, wspace=0.3)
    return fig


# The extraction figure's p-value axis stops here; anything smaller is drawn at the floor.
P_FLOOR = 1e-30
# Qubits from spike 0028: 88 carries a periodic disturbance, 34 switches like a telegraph.
EXTRACTION_QUBITS = (88, 34)


def _battery_points(bits: npt.NDArray[np.uint8]) -> dict[str, float]:
    """The battery's p-values, as log₁₀ rounded to two places: the last digits of erfc and
    lgamma differ between platforms, and the figure must render to the same bytes on each."""
    return {name: round(math.log10(max(p, P_FLOOR)), 2) for name, p in battery(bits).items()}


def extraction(runs: Path) -> Figure:
    """The battery on raw shots, von Neumann's output and Toeplitz's, for two misbehaving qubits."""
    run = load_run(runs / CHIP_MAP_RUN)
    if run.memory is None:
        raise ValueError(f"{runs / CHIP_MAP_RUN}: the chip map is expected to keep its memory")
    width = len(run.memory[0])
    shots = np.frombuffer("".join(run.memory).encode(), dtype=np.uint8).reshape(-1, width)
    # A fixed seed so the figure renders the same every time; harvests use the OS's.
    seed = np.random.default_rng(0).integers(0, 2, 2 * len(shots), dtype=np.uint8)

    fig = Figure(figsize=(8.4, 5.2))
    axes = fig.subplots(1, len(EXTRACTION_QUBITS), sharey=True)
    for ax, qubit in zip(axes, EXTRACTION_QUBITS, strict=True):
        column = width - 1 - run.qubits.index(qubit)  # classical bit 0 is rightmost
        raw = (shots[:, column] == ord("1")).astype(np.uint8)
        series = (
            ("raw shots", raw, INK, "x"),
            ("von Neumann", von_neumann(raw), MEASURED, "o"),
            ("Toeplitz", toeplitz_extract(raw, seed).bits, PREDICTED, "s"),
        )
        names: list[str] = []
        for offset, (label, bits, colour, marker) in zip((-0.22, 0, 0.22), series, strict=True):
            points = _battery_points(bits)
            names = list(points)
            ys = [i + offset for i in range(len(names))]
            ax.scatter(
                list(points.values()),
                ys,
                color=colour,
                marker=marker,
                s=28,
                label=f"{label} ({len(bits):,} bits)",
                zorder=2,
            )
        threshold = math.log10(ALPHA)
        ax.axvline(threshold, color=INK, lw=1, ls="--", zorder=1)
        ax.annotate(
            f"fails ← {ALPHA_SIGN} = {ALPHA}",
            (threshold, 1),
            xycoords=("data", "axes fraction"),
            xytext=(-4, 2),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=8,
        )
        floor = math.log10(P_FLOOR)
        ax.set_xlim(floor - 1, 0.5)
        ax.set_xticks([floor, -20, -10, 0], [f"≤10^{int(floor)}", "10^-20", "10^-10", "1"])
        ax.set_yticks(range(len(names)), names)
        ax.invert_yaxis()
        ax.set_title(f"qubit {qubit}", loc="left", fontsize=10)
        ax.set_xlabel("p-value (log scale)")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), fontsize=7, frameon=False)
    fig.suptitle("The test battery before and after extraction", x=0.01, ha="left", color=INK)
    fig.text(
        0.01,
        0.02,
        f"{run.shots:,} shots per qubit · {run.backend} · job {run.job_id} · "
        "Toeplitz seed fixed for the figure",
        fontsize=8,
    )
    fig.subplots_adjust(left=0.24, right=0.98, top=0.86, bottom=0.33, wspace=0.12)
    return fig


def chsh_test(runs: Path) -> Figure:
    """The CHSH run: each setting's correlation, and S against both bounds."""
    run = load_run(runs / CHSH_RUN)
    if run.prediction is None or run.memory is None:
        raise ValueError(f"{runs / CHSH_RUN}: a CHSH run carries a prediction and its shots")
    predicted = run.prediction.values
    counts = chsh.counts_by_setting(run.memory, run.extra["choices"])
    result = chsh.estimate(counts)
    measured = chsh.correlations_by_setting(counts)
    epsilon = predicted["epsilon"]
    s_low = result.lower_bound(epsilon)

    fig = Figure(figsize=(7.2, 3.4))
    left, right = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.15, 1]})

    labels = [f"E(a{i}, b{j})" for i, j in chsh.SETTINGS]
    for y, setting in enumerate(chsh.SETTINGS):
        e = measured[setting]
        n = sum(counts[setting].values())
        # A correlation is a binomial mean of ±1 outcomes: standard error √((1 − E²)/n).
        left.errorbar(
            e,
            y,
            xerr=math.sqrt((1 - e * e) / n),
            fmt="o",
            color=MEASURED,
            capsize=3,
            ms=6,
            label=f"measured, 1{SIGMA}" if y == 0 else None,
        )
        expected = predicted["correlations"][f"{setting[0]}{setting[1]}"]
        left.plot(
            expected,
            y,
            marker="|",
            ls="none",
            color=PREDICTED,
            ms=14,
            mew=2,
            label="predicted" if y == 0 else None,
        )
    left.axvline(0, color=INK, lw=1, ls="--", zorder=0)
    left.set_yticks(range(len(labels)), labels)
    left.invert_yaxis()
    left.set_xlim(-1, 1)
    left.set_xlabel(f"correlation: P(agree) {MINUS} P(differ)")
    left.set_title("each setting", loc="left", fontsize=10)
    left.legend(loc="lower right", fontsize=8, frameon=False)

    low, high = predicted["interval"]
    right.axhspan(low, high, color=PREDICTED, alpha=0.18, lw=0)
    right.errorbar(0, result.s, yerr=result.standard_error, fmt="o", color=MEASURED, capsize=4)
    right.plot([-0.25, 0.25], [s_low, s_low], color=MEASURED, lw=2, ls=":")
    for value, name in (
        (chsh.CLASSICAL_BOUND, "classical bound 2"),
        (chsh.TSIRELSON, "Tsirelson 2√2"),
    ):
        right.axhline(value, color=INK, lw=1, ls="--")
        right.annotate(
            name,
            (1, value),
            xycoords=("axes fraction", "data"),
            xytext=(-2, 3),
            textcoords="offset points",
            ha="right",
            fontsize=8,
        )
    right.annotate(
        f"S = {result.s:.3f} ± {result.standard_error:.3f}",
        (0, result.s),
        xytext=(10, 4),
        textcoords="offset points",
        fontsize=9,
        color=MEASURED,
    )
    right.annotate(
        f"S_low = {s_low:.3f}",
        (0.25, s_low),
        xytext=(4, -10),
        textcoords="offset points",
        fontsize=8,
        color=MEASURED,
    )
    right.annotate(
        f"predicted, 95%: {low:.3f} to {high:.3f}",
        (-0.95, low),
        xytext=(0, -11),
        textcoords="offset points",
        fontsize=8,
        color=PREDICTED,
    )
    right.set_xlim(-1, 1)
    right.set_xticks([])
    right.set_ylim(1.8, 3.0)
    right.set_ylabel("S")
    right.set_title("S against its bounds", loc="left", fontsize=10)
    fig.suptitle("The CHSH test on real hardware", x=0.01, ha="left", color=INK)
    fig.text(
        0.01,
        0.02,
        f"{result.rounds:,} rounds · S_low at ε = {epsilon:.1e} · prediction committed "
        f"before the run ({predicted['committed_as'][:7]}) · {run.backend} · qubits "
        f"{run.qubits[0]}, {run.qubits[1]} · job {run.job_id}",
        fontsize=8,
    )
    fig.subplots_adjust(left=0.14, right=0.97, top=0.84, bottom=0.2, wspace=0.28)
    return fig


# To add a figure: write a function from the runs directory to a Figure, and name its file
# here. `scripts/figures` renders it; commit the SVG it writes.
FIGURES: dict[str, Callable[[Path], Figure]] = {
    "first-coin.svg": first_coin,
    "chip-map.svg": chip_map,
    "prediction-scatter.svg": prediction_scatter,
    "extraction.svg": extraction,
    "chsh.svg": chsh_test,
}


def render(runs: Path, out: Path) -> list[Path]:
    """Render every figure from `runs` into `out`, and return the files written."""
    out.mkdir(parents=True, exist_ok=True)
    written = []
    with matplotlib.rc_context(STYLE):
        for name, draw in FIGURES.items():
            path = out / name
            draw(runs).savefig(path, format="svg", metadata=METADATA)
            written.append(path)
    return written


def check(runs: Path, committed: Path) -> list[str]:
    """Compare `committed` with a fresh render; return one line per file that disagrees."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = {path.name: path.read_bytes() for path in render(runs, Path(tmp))}
    present = {p.name: p for p in committed.iterdir() if p.is_file()} if committed.is_dir() else {}
    problems = []
    for name in sorted(fresh.keys() | present.keys()):
        path = committed / name
        if name not in present:
            problems.append(f"{path}: missing; run scripts/figures")
        elif name not in fresh:
            problems.append(f"{path}: no figure renders this file; remove it")
        elif present[name].read_bytes() != fresh[name]:
            problems.append(f"{path}: differs from the archive's render; run scripts/figures")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/figures", description="Render every figure from the archived runs."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="render to a temporary directory and fail if the committed figures differ",
    )
    parser.add_argument("--runs", type=Path, default=RUNS, help="archived runs (%(default)s)")
    parser.add_argument("--out", type=Path, default=FIGURES_DIR, help="figures (%(default)s)")
    args = parser.parse_args(argv)

    if args.check:
        problems = check(args.runs, args.out)
        for problem in problems:
            print(f"✗ {problem}", file=sys.stderr)
        if problems:
            return 1
        print(f"✓ {len(FIGURES)} figure(s) in {args.out} match the archive")
        return 0
    for path in render(args.runs, args.out):
        print(f"→ wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
