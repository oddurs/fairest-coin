"""Spike 0018: which error sources bias a one-gate coin, against a real calibration snapshot.

For every qubit with complete calibration, simulate H + measure with exactly one error source
switched on and report its contribution to P(tails) − 0.5.

    uv run python analysis/dominant_errors.py data/runs/2026-11-01-dbjsk29ffo6c73baaosg
"""

import statistics
import sys
from collections.abc import Callable

import numpy as np

from coin.archive import load_run
from coin.circuit import Circuit, Gate, Measure
from coin.noise import Readout, apply_readout, depolarizing, thermal_relaxation
from coin.sim import Channel, Noise, probabilities

COIN = Circuit(1).h(0).measure(0, 0)
# The same coin with an identity first, so preparation error can act before H.
PREPARED_COIN = Circuit(1).i(0).h(0).measure(0, 0)
REQUIRED = {"T1", "T2", "prob_meas1_prep0", "prob_meas0_prep1", "readout_length"}
X_FLIP = np.array([[0, 1], [1, 0]], dtype=np.complex128)

READOUT = "readout asymmetry"
GATE_DECAY = "T1/T2 during sx"
GATE_ERROR = "gate error (depolarizing)"
PREPARATION = "preparation error"
WINDOW = "T1 over the measurement window (double counts readout)"


def bias(circuit: Circuit, noise: Noise | None = None, readout: Readout | None = None) -> float:
    p = probabilities(circuit, noise)
    if readout is not None:
        p = apply_readout(p, {0: readout})
    return p.get("1", 0.0) - 0.5


def on(kind: type[Gate] | type[Measure], channels: tuple[Channel, ...]) -> Noise:
    return lambda op: channels if isinstance(op, kind) else ()


def on_identity(channel: Channel) -> Callable[[Gate | Measure], tuple[Channel, ...]]:
    return lambda op: (channel,) if isinstance(op, Gate) and op.name == "i" else ()


def main(run_dir: str) -> None:
    calibration = load_run(run_dir).calibration
    sx = {
        g["qubits"][0]: {p["name"]: p["value"] for p in g["parameters"]}
        for g in calibration["gates"]
        if g["gate"] == "sx"
    }
    rows: dict[str, list[float]] = {
        name: [] for name in (READOUT, GATE_DECAY, GATE_ERROR, PREPARATION, WINDOW)
    }
    incomplete: dict[int, list[str]] = {}
    unphysical: list[int] = []
    no_init_error: list[int] = []

    for q, props in enumerate(calibration["qubits"]):
        d = {p["name"]: p["value"] for p in props}
        if missing := REQUIRED - d.keys():
            incomplete[q] = sorted(missing)
            continue
        t1, t2 = d["T1"] * 1e3, d["T2"] * 1e3  # µs → ns, the unit of gate and readout lengths
        if t2 > 2 * t1:
            unphysical.append(q)
            continue

        readout = Readout(d["prob_meas1_prep0"], d["prob_meas0_prep1"])
        rows[READOUT].append(bias(COIN, readout=readout))
        relax = thermal_relaxation(t1, t2, sx[q]["gate_length"], 0)
        rows[GATE_DECAY].append(bias(COIN, on(Gate, relax)))
        # IBM's average gate error r relates to depolarizing p by r = p/2 for one qubit.
        scramble = depolarizing(min(1.0, 2 * sx[q]["gate_error"]), 0)
        rows[GATE_ERROR].append(bias(COIN, on(Gate, (scramble,))))
        if "init_error" in d:
            e = d["init_error"]
            flip = Channel(
                (np.sqrt(1 - e) * np.eye(2, dtype=np.complex128), np.sqrt(e) * X_FLIP), (0,)
            )
            rows[PREPARATION].append(bias(PREPARED_COIN, on_identity(flip)))
        else:
            no_init_error.append(q)
        window = thermal_relaxation(t1, t2, d["readout_length"], 0)
        rows[WINDOW].append(bias(COIN, on(Measure, window)))

    print(f"qubits analysed: {len(rows[READOUT])} of {len(calibration['qubits'])}")
    print(f"incomplete calibration (skipped): {incomplete}")
    print(f"T2 > 2·T1 (skipped): {unphysical}")
    print(f"no init_error (preparation row only): {no_init_error}")
    print(f"{'source':56} {'median':>9} {'max |·|':>9}")
    for name, values in rows.items():
        print(f"{name:56} {statistics.median(values):+9.5f} {max(abs(v) for v in values):9.5f}")


if __name__ == "__main__":
    main(sys.argv[1])
