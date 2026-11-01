"""The `coin` command."""

import argparse

from coin import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coin", description="Can you prove a coin flip is random?"
    )
    parser.add_argument("--version", action="version", version=f"coin {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
