"""The `coin` command."""

import argparse
import sys
from collections.abc import Callable

import numpy as np

from coin import __version__
from coin.circuit import Circuit
from coin.sim import sample

# The quantum coin: start at heads, |0⟩, apply H, measure.
COIN = Circuit(1).h(0).measure(0, 0)
FACES = {"0": "heads", "1": "tails"}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return _flip(args)


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
