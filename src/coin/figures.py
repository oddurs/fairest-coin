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
from matplotlib.figure import Figure
from matplotlib.typing import RcKeyType

from coin.archive import load_run

# Relative to the repository root, where scripts/figures runs from.
RUNS = Path("data/runs")
FIGURES_DIR = Path("docs/figures")

FIRST_RUN = "2026-11-01-dbjsk29ffo6c73baaosg"

# One grey for text, axes and neutral marks: about 4.3:1 against both GitHub's white
# and its dark #0d1117, because one SVG has to read on either background.
INK = "#7a7a7a"
# Mid-luminance, checked for colour-blind separation and 3:1 contrast on both themes.
MEASURED = "#3a80dc"
PREDICTED = "#e2622d"

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


# To add a figure: write a function from the runs directory to a Figure, and name its file
# here. `scripts/figures` renders it; commit the SVG it writes.
FIGURES: dict[str, Callable[[Path], Figure]] = {
    "first-coin.svg": first_coin,
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
