"""The `coin` command."""

import argparse
import gzip
import json
import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from coin import __version__
from coin.archive import ArchiveError, load_run
from coin.circuit import Circuit
from coin.noise import model_from_calibration, predict_tails
from coin.sim import sample

# The quantum coin: start at heads, |0⟩, apply H, measure.
COIN = Circuit(1).h(0).measure(0, 0)
# The same coin in IBM's native gates, as the hardware runs it: H = rz(π/2)·sx·rz(π/2).
NATIVE_COIN = Circuit(1).rz(math.pi / 2, 0).sx(0).rz(math.pi / 2, 0).measure(0, 0)
FACES = {"0": "heads", "1": "tails"}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.handler(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coin", description="Can you prove a coin flip is random?"
    )
    parser.add_argument("--version", action="version", version=f"coin {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    flip = commands.add_parser(
        "flip",
        help="flip the quantum coin",
        description="Flip a quantum coin: H on |0⟩, then measure. Heads is 0, tails is 1.",
    )
    flip.add_argument("--sim", action="store_true", help="flip on the built-in simulator")
    flip.add_argument(
        "--shots", type=_at_least(1), metavar="N", help="flip N times and print the counts"
    )
    flip.add_argument(
        "--seed",
        type=_at_least(0),
        metavar="S",
        help="seed the simulator's generator to replay a run",
    )
    flip.set_defaults(handler=_flip)

    predict = commands.add_parser(
        "predict",
        help="predict every qubit's coin from calibration data",
        description="Predict P(tails) for the coin on every qubit of a calibration snapshot, "
        "from readout error and decay during gates. Qubits with incomplete or unphysical "
        "calibration are listed, not guessed.",
    )
    predict.add_argument(
        "--calibration",
        required=True,
        type=Path,
        metavar="PATH",
        help="an archived run directory, or a calibration .json or .json.gz file",
    )
    predict.add_argument(
        "--measurement-decay",
        action="store_true",
        help="also apply decay over the readout window (the double-counting alternative)",
    )
    predict.set_defaults(handler=_predict)
    return parser


def _at_least(minimum: int) -> Callable[[str], int]:
    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a whole number: {text!r}") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"must be at least {minimum}, got {value}")
        return value

    return parse


def _flip(args: argparse.Namespace) -> int:
    if not args.sim:
        print(
            "coin flip: real hardware arrives in v0.2; pass --sim to flip on the simulator",
            file=sys.stderr,
        )
        return 2
    rng = np.random.default_rng(args.seed)
    if args.shots is None:
        (outcome,) = sample(COIN, 1, rng)
        print(FACES[outcome].upper())
        return 0
    counts = sample(COIN, args.shots, rng)
    width = len(f"{args.shots:,}")
    for outcome, face in FACES.items():
        n = counts.get(outcome, 0)
        print(f"{face}  {n:>{width},}  {n / args.shots:7.2%}")
    return 0


def _predict(args: argparse.Namespace) -> int:
    try:
        model = model_from_calibration(_read_calibration(args.calibration))
    except (OSError, ValueError, ArchiveError) as error:
        print(f"coin predict: cannot read calibration: {error}", file=sys.stderr)
        return 1
    tails = {
        q: predict_tails(noise, NATIVE_COIN, measurement_decay=args.measurement_decay)
        for q, noise in model.qubits.items()
    }
    print("qubit  P(tails)    bias")
    for q, p in sorted(tails.items(), key=lambda item: (item[1], item[0])):
        print(f"{q:>5}  {p:8.5f}  {p - 0.5:+7.2%}")
    for q, reason in sorted(model.excluded.items()):
        print(f"{q:>5}  excluded: {reason}")
    return 0


def _read_calibration(path: Path) -> dict[str, Any]:
    if path.is_dir():
        return load_run(path).calibration
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(raw)
