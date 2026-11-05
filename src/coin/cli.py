"""The `coin` command."""

import argparse
import gzip
import json
import math
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from coin import __version__, bell, certify, chipmap, chsh, commitment, harvest, readout
from coin.archive import ArchiveError, load_run
from coin.chipmap import MAX_SHOTS
from coin.circuit import Circuit
from coin.hardware import Fetcher, Transport, discard, pending_runs, recover, submit
from coin.noise import model_from_calibration, predict_tails
from coin.pool import POOL_ENV, EmptyPoolError, Pool, receipt
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
    _add_flip(commands)

    pool = commands.add_parser(
        "pool",
        help="show the entropy pool",
        description="Show each harvested batch in the entropy pool and how much of it is spent.",
    )
    pool.add_argument("--pool", type=Path, metavar="DIR", help=f"the entropy pool (${POOL_ENV})")
    pool.set_defaults(handler=_pool)

    harvest_ = commands.add_parser(
        "harvest",
        help="flip one qubit many times on IBM hardware and pool the extracted bits",
        description="Run the coin on the qubit whose readout errs least, archive the raw run, "
        "extract near-uniform bits by Toeplitz hashing, and add them to the entropy pool. "
        "Needs QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE. Spends QPU time only with --submit.",
    )
    harvest_.add_argument("--backend", metavar="NAME")
    harvest_.add_argument("--shots", type=_at_least(1), metavar="N", help=f"at most {MAX_SHOTS:,}")
    harvest_mode = harvest_.add_mutually_exclusive_group()
    harvest_mode.add_argument(
        "--dry-run", action="store_true", help="print the plan and its cost; submit nothing"
    )
    harvest_mode.add_argument(
        "--submit", action="store_true", help="predict, submit, archive, extract and pool"
    )
    harvest_.add_argument(
        "--runs-dir", type=Path, default=Path("data/runs"), metavar="DIR", help="the archive"
    )
    harvest_.add_argument(
        "--pool", type=Path, metavar="DIR", help=f"the entropy pool (${POOL_ENV})"
    )
    harvest_mode.add_argument(
        "--from-run",
        type=Path,
        metavar="DIR",
        help="extract an already archived one-qubit run instead of running a new job",
    )
    harvest_.set_defaults(handler=_harvest)

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
    predict.add_argument(
        "--pairs",
        action="store_true",
        help="rank coupled qubit pairs by the CHSH value S the noise model predicts",
    )
    predict.add_argument(
        "--readout",
        nargs=2,
        type=Path,
        metavar=("ZERO_RUN", "ONE_RUN"),
        help="with --pairs: archived prepare-|0⟩ and prepare-|1⟩ readout runs, whose measured "
        "readout replaces the published one",
    )
    predict.set_defaults(handler=_predict)

    compare = commands.add_parser(
        "compare",
        help="compare an archived chip map with its prediction",
        description="Read an archived chip-map run and report how its measurements compare "
        "with the prediction written before it ran. Reads only the archive.",
    )
    compare.add_argument("run_dir", type=Path, metavar="RUN", help="an archived run directory")
    compare.set_defaults(handler=_compare)

    _add_archive_commands(commands)

    run = commands.add_parser("run", help="run an experiment on real IBM hardware")
    experiments = run.add_subparsers(dest="experiment", required=True, metavar="EXPERIMENT")
    chip_map = experiments.add_parser(
        "chip-map",
        help="flip every qubit of a backend at once, predicted first",
        description="Predict every qubit's coin from the backend's current calibration, then "
        "flip them all in one job. Needs QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE. "
        "Spends QPU time only with --submit.",
    )
    chip_map.add_argument("--backend", required=True, metavar="NAME")
    chip_map.add_argument(
        "--shots",
        type=_at_least(1),
        required=True,
        metavar="N",
        help=f"shots per qubit, at most {MAX_SHOTS:,}",
    )
    mode = chip_map.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run", action="store_true", help="print the plan and its cost; submit nothing"
    )
    mode.add_argument(
        "--submit", action="store_true", help="predict, then submit and archive the job"
    )
    chip_map.add_argument(
        "--runs-dir", type=Path, default=Path("data/runs"), metavar="DIR", help="the archive"
    )
    chip_map.set_defaults(handler=_chip_map)

    readout_ = experiments.add_parser(
        "readout",
        help="prepare |0⟩ or |1⟩ on every qubit and measure: the readout as a job sees it",
        description="Prepare |0⟩ (or |1⟩ with --prepare 1) on every qubit of a backend and "
        "measure them all at once, predicted first from the published readout error. "
        "Needs QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE. Spends QPU time only with --submit.",
    )
    readout_.add_argument("--backend", required=True, metavar="NAME")
    readout_.add_argument(
        "--shots", type=_at_least(1), required=True, metavar="N", help=f"at most {MAX_SHOTS:,}"
    )
    readout_.add_argument(
        "--prepare", type=int, choices=(0, 1), required=True, help="the state to prepare"
    )
    readout_mode = readout_.add_mutually_exclusive_group(required=True)
    readout_mode.add_argument(
        "--dry-run", action="store_true", help="print the plan and its cost; submit nothing"
    )
    readout_mode.add_argument(
        "--submit", action="store_true", help="predict, then submit and archive the job"
    )
    readout_.add_argument(
        "--runs-dir", type=Path, default=Path("data/runs"), metavar="DIR", help="the archive"
    )
    readout_.set_defaults(handler=_readout)

    _add_bell(experiments)
    _add_chsh(experiments)
    return parser


def _add_archive_commands(commands: Any) -> None:
    """`coin publish` and `coin recover`: looking after what is already in the archive."""
    publish = commands.add_parser(
        "publish",
        help="write a spent batch's extraction record into its archived run",
        description="Once a harvest's or a certified CHSH run's pool batch is spent, write the "
        "batch's provenance (its seed included) into the run's directory as extraction.json, "
        "so that every flip it gave can be recomputed from the archive. Refused while any bit "
        "is unspent.",
    )
    publish.add_argument("run_dir", type=Path, metavar="RUN", help="the archived run")
    publish.add_argument("--pool", type=Path, metavar="DIR", help=f"the entropy pool (${POOL_ENV})")
    publish.set_defaults(handler=_publish)

    certify_ = commands.add_parser(
        "certify",
        help="hash a CHSH run's outcomes at the rate its S_low certifies, into the pool",
        description="For a CHSH run whose settings came from the pool, bound S below at the "
        "run's ε; if S_low exceeds 2, hash its outcome bits at the min-entropy that certifies "
        "and add them to the pool as a certified batch. Reports the setting bits spent, the "
        "certified bits made, and the net. Refused once the run is committed to git.",
    )
    certify_.add_argument("run_dir", type=Path, metavar="RUN", help="the archived CHSH run")
    certify_.add_argument(
        "--pool", type=Path, metavar="DIR", help=f"the entropy pool (${POOL_ENV})"
    )
    certify_.set_defaults(handler=_certify)

    recover = commands.add_parser(
        "recover",
        help="archive a hardware job whose run was cut short",
        description="Archive a job that IBM accepted but whose run did not finish archiving "
        "(the wait timed out, the connection dropped, or it was interrupted), from the pending "
        "record written before it was submitted. Fetches the result from IBM if the record "
        "does not already hold it; needs QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE then.",
    )
    recover.add_argument(
        "job_id", metavar="JOB_ID", nargs="?", help="the job to archive; omit to list"
    )
    recover.add_argument(
        "--runs-dir", type=Path, default=Path("data/runs"), metavar="DIR", help="the archive"
    )
    recover.add_argument(
        "--record",
        type=Path,
        metavar="FILE",
        help="the pending record to use, for a job whose id was never recorded",
    )
    recover.add_argument(
        "--force",
        action="store_true",
        help="recover a job its submitter still holds, or discard a record that names a job",
    )
    recover.add_argument(
        "--discard",
        type=Path,
        metavar="FILE",
        help="remove a pending record for a job that never ran",
    )
    recover.set_defaults(handler=_recover)


def _add_flip(commands: Any) -> None:
    flip = commands.add_parser(
        "flip",
        help="flip the quantum coin",
        description="Flip a quantum coin. With --sim, H on |0⟩ then measure, simulated. "
        "Without it, spend bits harvested from real hardware (`coin harvest`). "
        "Heads is 0, tails is 1.",
    )
    flip.add_argument(
        "--sim",
        action="store_true",
        help="flip on the built-in simulator; without it, spend bits from the entropy pool",
    )
    flip.add_argument(
        "--shots", type=_at_least(1), metavar="N", help="flip N times and print the counts"
    )
    flip.add_argument(
        "--seed",
        type=_at_least(0),
        metavar="S",
        help="seed the simulator's generator to replay a run",
    )
    flip.add_argument("--pool", type=Path, metavar="DIR", help=f"the entropy pool (${POOL_ENV})")
    output = flip.add_mutually_exclusive_group()
    output.add_argument(
        "--json",
        action="store_true",
        help="print the flip's receipt as JSON (docs/receipt.schema.json)",
    )
    output.add_argument("--quiet", action="store_true", help="print only HEADS or TAILS")
    flip.set_defaults(handler=_flip)


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
        return _flip_from_pool(args)
    if args.json:
        print("coin flip: --json is a hardware flip's receipt; --sim has none", file=sys.stderr)
        return 2
    if args.pool is not None:
        print("coin flip: --pool is for pool bits; it cannot go with --sim", file=sys.stderr)
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


def _flip_from_pool(args: argparse.Namespace) -> int:
    if args.seed is not None:
        print("coin flip: --seed replays the simulator; it needs --sim", file=sys.stderr)
        return 2
    if args.shots is not None and (args.json or args.quiet):
        print("coin flip: --json and --quiet describe one flip; leave out --shots", file=sys.stderr)
        return 2
    try:
        draws = Pool(args.pool).take(args.shots or 1)
    except EmptyPoolError as error:
        print(f"coin flip: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as error:
        print(f"coin flip: the pool could not be read: {error!r}", file=sys.stderr)
        return 1
    bits = np.concatenate([d.bits for d in draws])
    if args.shots is None:
        (draw,) = draws
        flip = receipt(draw, datetime.now(UTC))
        if args.json:
            print(json.dumps(flip, indent=2))
        elif args.quiet:
            print(flip["outcome"])
        else:
            print(flip["outcome"])
            print(
                f"  {flip['backend']} · qubit {flip['qubit']} · job {flip['job_id']} · "
                f"harvested {str(flip['harvested_at'])[:10]}"
            )
            print(
                f"  run {flip['run']} · bit {flip['offset'] + 1:,} of {flip['batch_bits']:,} "
                f"in batch {flip['batch']}"
            )
            print(
                f"  Toeplitz extraction at {flip['entropy_per_bit']:.4f} bits per shot, "
                f"ε = {flip['epsilon']:.1e} if the estimate holds"
            )
        return 0
    width = len(f"{args.shots:,}")
    for outcome, face in FACES.items():
        n = int(np.count_nonzero(bits == int(outcome)))
        print(f"{face}  {n:>{width},}  {n / args.shots:7.2%}")
    return 0


def _pool(args: argparse.Namespace) -> int:
    try:
        batches = Pool(args.pool).status()
    except (OSError, ValueError, KeyError) as error:
        print(f"coin pool: the pool could not be read: {error!r}", file=sys.stderr)
        return 1
    if not batches:
        print("the pool is empty; run `coin harvest` to fill it")
        return 0
    # Batch names carry the time to the microsecond, so size the column to them.
    w = max(len("batch"), *(len(b.batch) for b in batches))
    print(f"{'batch':<{w}} {'qubit':>5} {'bits':>8} {'spent':>8} {'remaining':>10}")
    for b in batches:
        print(
            f"{b.batch:<{w}} {b.provenance.get('qubit', '?'):>5} {b.total:>8,} {b.spent:>8,} "
            f"{b.remaining:>10,}"
        )
    print(
        f"{'total':<{w}} {'':>5} {sum(b.total for b in batches):>8,} "
        f"{sum(b.spent for b in batches):>8,} {sum(b.remaining for b in batches):>10,}"
    )
    return 0


def _harvest(args: argparse.Namespace) -> int:
    if args.from_run is not None:
        return _harvest_from_run(args)
    return _harvest_new(args)


def _why_public(path: Path) -> str | None:
    """Why `path`'s shots may be public, or None when git has never seen them."""
    where = path.resolve()
    folder = where if where.is_dir() else where.parent
    if not any((d / ".git").exists() for d in (folder, *folder.parents)):
        return None  # outside every repository, nothing could have been committed
    # Git's own variables (set, for one, while a hook runs) would point it at another
    # repository than the one `path` is in; let it find the right one from `path`.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--", str(where)],
            cwd=folder,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as error:
        detail = str(error)
    else:
        if listed.returncode == 0:
            if not listed.stdout.strip():
                return None
            return (
                "is tracked by git, so its shots are public and its bits would be "
                "predictable; use a run that has not been committed"
            )
        detail = listed.stderr.strip() or f"git exited {listed.returncode}"
    # Inside a repository an unanswered question is not a no.
    return (
        f"is inside a git repository, but git could not say whether it is tracked "
        f"({detail}); fix that, or harvest a run kept outside the repository"
    )


def _harvest_from_run(args: argparse.Namespace) -> int:
    if (why := _why_public(args.from_run)) is not None:
        print(f"coin harvest: {args.from_run} {why}", file=sys.stderr)
        return 1
    try:
        result = harvest.extract_run(args.from_run, Pool(args.pool))
    except (OSError, ValueError, ArchiveError) as error:
        print(f"coin harvest: {_explain(error)}", file=sys.stderr)
        return 1
    # The run was archived when it ran; this only extracted from it.
    _report_harvest(result, archived=False)
    return 0


def _harvest_new(args: argparse.Namespace) -> int:  # noqa: PLR0911 - each return is one way out
    pool = Pool(args.pool)
    if args.backend is None or args.shots is None or not (args.dry_run or args.submit):
        print(
            "coin harvest: give --backend, --shots and one of --dry-run or --submit, "
            "or --from-run DIR",
            file=sys.stderr,
        )
        return 2
    if args.shots > MAX_SHOTS:
        print(f"coin harvest: at most {MAX_SHOTS:,} shots per job", file=sys.stderr)
        return 2
    try:
        transport = _transport()
        chosen = harvest.plan(args.backend, transport.calibration(args.backend), args.shots)
        print(f"backend      {args.backend}")
        print(f"qubit        {chosen.qubit}, the one whose calibrated readout errs least")
        print(f"predicted    P(tails) = {chosen.p_tails:.4f}")
        print(
            f"shots        {args.shots:,}, forecast {chosen.expected_bits:,} bits after "
            "extraction (fewer if the qubit misbehaves)"
        )
        print(f"estimated    ~{chipmap.estimate_qpu_seconds(args.shots):.0f} QPU seconds")
        if chosen.expected_bits < harvest.MIN_HARVEST_BITS:
            print(
                f"coin harvest: forecast under {harvest.MIN_HARVEST_BITS:,} bits; "
                "ask for more shots",
                file=sys.stderr,
            )
            return 1
        if args.dry_run:
            print("dry run: nothing submitted")
            return 0
        command = " ".join(
            [
                f"coin harvest --backend {args.backend} --shots {args.shots} --submit",
                f"--runs-dir {args.runs_dir}",
                *([f"--pool {args.pool}"] if args.pool is not None else []),
            ]
        )
        result = harvest.harvest(transport, chosen, args.runs_dir, pool, submit_script=command)
    except ImportError as error:
        print(f"coin harvest: install the ibm extra ({error})", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, ArchiveError, OSError) as error:
        print(f"coin harvest: {_explain(error)}", file=sys.stderr)
        return 1
    _report_harvest(result)
    return 0


def _report_harvest(result: harvest.Harvest, *, archived: bool = True) -> None:
    e = result.extraction
    print(f"{'archived' if archived else 'run':<12} {result.run_dir}")
    print(
        f"extracted    {len(e.bits):,} bits: min-entropy estimate {e.estimate:.4f} per shot, "
        f"half spent (ε = {e.epsilon:.1e} if the estimate holds)"
    )
    print(f"pooled       batch {result.batch}")
    print(
        "note         the run's shots and the batch's seed determine every bit: commit the run "
        "only once the batch is spent"
    )


def _predict(args: argparse.Namespace) -> int:
    if args.readout and not args.pairs:
        print("coin predict: --readout is for --pairs", file=sys.stderr)
        return 2
    try:
        calibration = _read_calibration(args.calibration)
        model = model_from_calibration(calibration)
    except (OSError, ValueError, ArchiveError) as error:
        print(f"coin predict: cannot read calibration: {error}", file=sys.stderr)
        return 1
    if args.pairs:
        return _predict_pairs(calibration, args.readout)
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


# How many of the best pairs `coin predict --pairs` lists.
_TOP_PAIRS = 5


def _predict_pairs(calibration: dict[str, Any], readout_runs: list[Path] | None) -> int:
    try:
        measured_readout = (
            readout.measured(load_run(readout_runs[0]), load_run(readout_runs[1]))
            if readout_runs
            else None
        )
    except (OSError, ValueError, ArchiveError) as error:
        print(f"coin predict: cannot read the readout runs: {error}", file=sys.stderr)
        return 1
    ranked = chsh.rank_pairs(calibration, measured_readout)
    print(f"{len(ranked)} coupled pairs scored; the best {min(_TOP_PAIRS, len(ranked))}:")
    print("    pair  predicted S  cz error  readout")
    for score in ranked[:_TOP_PAIRS]:
        a, b = score.pair
        print(
            f"{a:>4}-{b:<4} {score.s:11.4f}  {score.cz_error:8.5f}  "
            f"{score.readout_source[0]}, {score.readout_source[1]}"
        )
    return 0


def _read_calibration(path: Path) -> dict[str, Any]:
    if path.is_dir():
        return load_run(path).calibration
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(raw)


def _compare(args: argparse.Namespace) -> int:
    try:
        run = load_run(args.run_dir)
        purpose = run.prediction.values.get("purpose") if run.prediction else None
        reports = {bell.PURPOSE: bell.report, bell.CHSH_PURPOSE: bell.chsh_report}
        print(reports.get(purpose, chipmap.report)(run))
    except (OSError, ValueError, ArchiveError) as error:
        print(f"coin compare: {error}", file=sys.stderr)
        return 1
    return 0


def _fetcher() -> Fetcher:
    # Imported here, like _transport, so that every other command works without Qiskit.
    from coin.ibm import IBMTransport  # noqa: PLC0415

    return IBMTransport()


def _transport() -> Transport:
    # Imported here so that every other command works without the `ibm` extra.
    from coin.ibm import IBMTransport  # noqa: PLC0415

    return IBMTransport()


def _explain(error: BaseException) -> str:
    """An error and its notes: `submit` notes how to recover a job it could not archive."""
    return "\n".join([str(error), *getattr(error, "__notes__", [])])


def _certify(args: argparse.Namespace) -> int:
    if (why := _why_public(args.run_dir)) is not None:
        print(f"coin certify: {args.run_dir} {why}", file=sys.stderr)
        return 1
    try:
        result = certify.certify(args.run_dir, Pool(args.pool))
    except (OSError, ValueError, ArchiveError) as error:
        print(f"coin certify: {_explain(error)}", file=sys.stderr)
        return 1
    print(certify.report(result))
    return 0


def _publish(args: argparse.Namespace) -> int:
    try:
        written = harvest.publish(args.run_dir, Pool(args.pool))
    except (OSError, ValueError, ArchiveError) as error:
        print(f"coin publish: {_explain(error)}", file=sys.stderr)
        return 1
    print(f"published    {written}")
    print("note         commit the run with this file: every flip it gave can now be checked")
    return 0


def _recover(args: argparse.Namespace) -> int:
    if args.discard is not None:
        try:
            discard(args.discard, force=args.force)
        except (OSError, ValueError) as error:
            print(f"coin recover: {error}", file=sys.stderr)
            return 1
        print(f"discarded    {args.discard}")
        return 0
    if args.job_id is None:
        waiting = pending_runs(args.runs_dir)
        if not waiting:
            print(f"no jobs are waiting to be archived for {args.runs_dir}")
        for p in waiting:
            if p.record is None:
                print(f"{p.path}  {p.problem}")
                continue
            job = p.record.get("job_id") or "(no job id recorded)"
            print(f"{job}  {p.record['backend']}  submitted {p.record['submitted_at']}  {p.path}")
        return 0
    try:
        directory = recover(_fetcher, args.job_id, args.runs_dir, args.record, force=args.force)
    except ImportError as error:
        print(f"coin recover: install the ibm extra ({error})", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, ArchiveError) as error:
        print(f"coin recover: {_explain(error)}", file=sys.stderr)
        return 1
    print(f"archived     {directory}")
    run = load_run(directory)
    if run.prediction is not None and run.prediction.values.get("purpose") == "harvest":
        print(f"next         `coin harvest --from-run {directory}` adds its bits to the pool")
    return 0


def _readout(args: argparse.Namespace) -> int:
    if args.shots > MAX_SHOTS:
        print(f"coin run readout: at most {MAX_SHOTS:,} shots per job", file=sys.stderr)
        return 2
    try:
        transport = _transport()
        chosen = readout.plan(
            args.backend, transport.calibration(args.backend), args.shots, args.prepare
        )
        print(readout.summary(chosen))
        print(f"estimated    ~{chipmap.estimate_qpu_seconds(args.shots):.0f} QPU seconds")
        if args.dry_run:
            print("dry run: nothing submitted")
            return 0
        command = (
            f"coin run readout --backend {args.backend} --shots {args.shots} "
            f"--prepare {args.prepare} --submit --runs-dir {args.runs_dir}"
        )
        directory = submit(transport, chosen.submission, args.runs_dir, submit_script=command)
        hits, total = readout.within_three_sigma(load_run(directory))
    except ImportError as error:
        print(f"coin run: install the ibm extra ({error})", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, ArchiveError) as error:
        print(f"coin run readout: {_explain(error)}", file=sys.stderr)
        return 1
    print(f"archived     {directory}")
    print(f"published    {hits} of {total} qubits read within 3σ of their published error")  # noqa: RUF001 - σ is the display text
    return 0


def _add_bell(experiments: Any) -> None:
    bell_ = experiments.add_parser(
        "bell",
        help="entangle two qubits and read both: two coins that always agree",
        description="Prepare the Bell pair on the coupled pair with the best predicted CHSH "
        "value (or --pair), read both qubits, and archive the run, predicted first. Needs "
        "QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE. Spends QPU time only with --submit.",
    )
    bell_.add_argument("--backend", required=True, metavar="NAME")
    bell_.add_argument(
        "--shots", type=_at_least(1), required=True, metavar="N", help=f"at most {MAX_SHOTS:,}"
    )
    bell_.add_argument(
        "--pair", nargs=2, type=int, metavar=("A", "B"), help="a coupled pair to use instead"
    )
    bell_.add_argument(
        "--readout",
        nargs=2,
        type=Path,
        metavar=("ZERO_RUN", "ONE_RUN"),
        help="archived prepare-|0⟩ and prepare-|1⟩ readout runs to predict with",
    )
    bell_mode = bell_.add_mutually_exclusive_group(required=True)
    bell_mode.add_argument(
        "--dry-run", action="store_true", help="print the plan and its cost; submit nothing"
    )
    bell_mode.add_argument(
        "--submit", action="store_true", help="predict, then submit and archive the job"
    )
    bell_.add_argument(
        "--runs-dir", type=Path, default=Path("data/runs"), metavar="DIR", help="the archive"
    )
    bell_.set_defaults(handler=_bell)


def _add_chsh(experiments: Any) -> None:
    chsh_ = experiments.add_parser(
        "chsh",
        help="the CHSH test: predict S, commit the prediction, then measure",
        description="The CHSH test on the coupled pair with the best predicted S (or --pair), "
        "each round's setting drawn uniformly by the operating system, all four interleaved "
        "in one job. --predict writes the whole plan and its predicted S, with a 95%% interval "
        "from the measured readout, to a file; commit and push it; then --submit --prediction "
        "FILE runs exactly that plan, and refuses while the file is uncommitted. Needs "
        "QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE. Spends QPU time only with --submit.",
    )
    chsh_.add_argument("--backend", metavar="NAME", help="for --dry-run and --predict")
    chsh_.add_argument("--rounds", type=_at_least(1), metavar="N", help=f"at most {MAX_SHOTS:,}")
    chsh_.add_argument(
        "--pair", nargs=2, type=int, metavar=("A", "B"), help="a coupled pair to use instead"
    )
    chsh_.add_argument(
        "--readout",
        nargs=2,
        type=Path,
        metavar=("ZERO_RUN", "ONE_RUN"),
        help="archived prepare-|0⟩ and prepare-|1⟩ readout runs to predict with",
    )
    mode = chsh_.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run", action="store_true", help="print the plan and its cost; write nothing"
    )
    mode.add_argument(
        "--predict", action="store_true", help="write the plan and its prediction to a file"
    )
    mode.add_argument(
        "--submit", action="store_true", help="run a committed prediction and archive the run"
    )
    chsh_.add_argument("--prediction", type=Path, metavar="FILE", help="for --submit")
    chsh_.add_argument(
        "--predictions-dir",
        type=Path,
        default=Path("data/predictions"),
        metavar="DIR",
        help="where --predict writes",
    )
    chsh_.add_argument(
        "--runs-dir", type=Path, default=Path("data/runs"), metavar="DIR", help="the archive"
    )
    chsh_.add_argument(
        "--pool",
        type=Path,
        metavar="DIR",
        help=f"the entropy pool --predict draws settings from (${POOL_ENV})",
    )
    chsh_.set_defaults(handler=_chsh)


def _chsh(args: argparse.Namespace) -> int:
    if args.submit:
        if args.prediction is None:
            print("coin run chsh: --submit runs a committed --prediction FILE", file=sys.stderr)
            return 2
        return _chsh_submit(args)
    if args.backend is None or args.rounds is None:
        print("coin run chsh: --dry-run and --predict need --backend and --rounds", file=sys.stderr)
        return 2
    if args.predict and args.readout is None:
        print(
            "coin run chsh: --predict needs --readout: the prediction's interval rests on "
            "readout measured in the same session",
            file=sys.stderr,
        )
        return 2
    return _chsh_plan(args)


def _chsh_plan(args: argparse.Namespace) -> int:
    try:
        measured_readout = (
            readout.measured_counts(load_run(args.readout[0]), load_run(args.readout[1]))
            if args.readout
            else None
        )
        transport = _transport()
        calibration = transport.calibration(args.backend)
        pair = tuple(args.pair) if args.pair else None
        # Planned first with throwaway settings: anything that would stop the run is found
        # before a single pool bit is spent on its settings.
        chosen = bell.plan_chsh(
            args.backend,
            calibration,
            bell.random_choices(args.rounds),
            pair=pair,
            measured=measured_readout,
        )
        print(bell.chsh_summary(chosen))
        if args.dry_run:
            print("dry run: nothing written, nothing submitted, no pool bit spent")
            return 0
        if chosen.interval is None:
            print("coin run chsh: the chosen pair's readout was not measured", file=sys.stderr)
            return 1
        choices, sources = certify.settings_from_pool(Pool(args.pool), args.rounds)
        chosen = bell.plan_chsh(
            args.backend, calibration, choices, pair=chosen.pair, measured=measured_readout
        )
        values = {
            **chosen.submission.prediction.values,
            "settings_source": {"pool": sources},
        }
        prediction = replace(chosen.submission.prediction, values=values)
        chosen = replace(chosen, submission=replace(chosen.submission, prediction=prediction))
        print(f"settings     {len(choices) * certify.BITS_PER_ROUND:,} pool bits spent")
        path = bell.save_prediction(chosen, args.predictions_dir)
    except ImportError as error:
        print(f"coin run: install the ibm extra ({error})", file=sys.stderr)
        return 1
    except EmptyPoolError as error:
        print(f"coin run chsh: the settings come from the pool: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, ArchiveError) as error:
        print(f"coin run chsh: {_explain(error)}", file=sys.stderr)
        return 1
    print(f"predicted    {path}")
    print(f"next         commit and push it, then: coin run chsh --submit --prediction {path}")
    return 0


def _chsh_submit(args: argparse.Namespace) -> int:
    try:
        chosen = bell.load_prediction(args.prediction)
        commit = commitment.committed(args.prediction)
        values = {
            **chosen.submission.prediction.values,
            "committed_as": commit,
            "prediction_file": str(args.prediction),
        }
        prediction = replace(chosen.submission.prediction, values=values)
        submission = replace(chosen.submission, prediction=prediction)
        print(bell.chsh_summary(chosen))
        print(f"committed    {commit}")
        command = (
            f"coin run chsh --submit --prediction {args.prediction} --runs-dir {args.runs_dir}"
        )
        transport = _transport()
        directory = submit(transport, submission, args.runs_dir, submit_script=command)
        result = bell.chsh_report(load_run(directory))
    except ImportError as error:
        print(f"coin run: install the ibm extra ({error})", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, ArchiveError) as error:
        print(f"coin run chsh: {_explain(error)}", file=sys.stderr)
        return 1
    print(f"archived     {directory}")
    print(result)
    return 0


def _bell(args: argparse.Namespace) -> int:
    try:
        measured_readout = (
            readout.measured(load_run(args.readout[0]), load_run(args.readout[1]))
            if args.readout
            else None
        )
        transport = _transport()
        chosen = bell.plan(
            args.backend,
            transport.calibration(args.backend),
            args.shots,
            pair=tuple(args.pair) if args.pair else None,
            measured=measured_readout,
        )
        print(bell.summary(chosen))
        if args.dry_run:
            print("dry run: nothing submitted")
            return 0
        a, b = chosen.pair
        command = (
            f"coin run bell --backend {args.backend} --shots {args.shots} --pair {a} {b} "
            f"--submit --runs-dir {args.runs_dir}"
        )
        if args.readout:
            command += f" --readout {args.readout[0]} {args.readout[1]}"
        directory = submit(transport, chosen.submission, args.runs_dir, submit_script=command)
        result = bell.report(load_run(directory))
    except ImportError as error:
        print(f"coin run: install the ibm extra ({error})", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, ArchiveError) as error:
        print(f"coin run bell: {_explain(error)}", file=sys.stderr)
        return 1
    print(f"archived     {directory}")
    print(result)
    return 0


def _chip_map(args: argparse.Namespace) -> int:
    if args.shots > MAX_SHOTS:
        print(f"coin run chip-map: at most {MAX_SHOTS:,} shots per job", file=sys.stderr)
        return 2
    try:
        transport = _transport()
        chip = chipmap.plan(args.backend, transport.calibration(args.backend), args.shots)
        print(chipmap.summary(chip))
        if args.dry_run:
            print("dry run: nothing submitted")
            return 0
        command = f"coin run chip-map --backend {args.backend} --shots {args.shots} --submit"
        directory = submit(transport, chip.submission, args.runs_dir, submit_script=command)
    except ImportError as error:
        print(f"coin run: install the ibm extra ({error})", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, ArchiveError) as error:
        print(f"coin run chip-map: {_explain(error)}", file=sys.stderr)
        return 1
    run = load_run(directory)
    tails = chipmap.tails_by_qubit(run)
    print(f"archived     {directory}")
    for label, predicted in (
        ("model", chip.p_tails),
        ("alternative", chip.p_tails_measurement_decay),
    ):
        within = sum(
            chipmap.within_three_sigma(tails[q] / run.shots, p, run.shots)
            for q, p in predicted.items()
        )
        print(f"{label:12} {within} of {len(predicted)} qubits within 3σ of the prediction")  # noqa: RUF001 - σ is the display text
    return 0
