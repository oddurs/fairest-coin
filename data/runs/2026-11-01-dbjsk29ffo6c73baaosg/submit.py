"""Spike 0015: one quantum coin on real IBM hardware, predicted first, archived whole.

Usage: python submit.py OUT_DIR BACKEND [--submit]

Without --submit it stops after writing the calibration snapshot and the prediction, and
prints the circuit that would run. The credentials come from QISKIT_IBM_TOKEN and
QISKIT_IBM_INSTANCE and are never written or printed.
"""

import json
import math
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from qiskit import qasm3, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from qiskit_ibm_runtime import __version__ as runtime_version

SHOTS = 4096

# H lowered by hand to the native basis: H = rz(π/2)·sx·rz(π/2) up to a global phase.
COIN_QASM = """OPENQASM 3.0;
include "stdgates.inc";
qubit[1] q;
bit[1] c;
rz(pi/2) q[0];
sx q[0];
rz(pi/2) q[0];
c[0] = measure q[0];
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def main() -> None:
    out, backend_name = Path(sys.argv[1]), sys.argv[2]
    submit = "--submit" in sys.argv[3:]
    out.mkdir(parents=True, exist_ok=False)

    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=os.environ["QISKIT_IBM_TOKEN"],
        instance=os.environ["QISKIT_IBM_INSTANCE"],
    )
    backend = service.backend(backend_name)
    props = backend.properties()
    write_json(out / "calibration.json", props.to_dict())

    # The qubit whose readout is most symmetric and accurate is the fairest coin on offer.
    def readout(q: int) -> tuple[float, float]:
        p1_given_0 = props.qubit_property(q, "prob_meas1_prep0")[0]
        p0_given_1 = props.qubit_property(q, "prob_meas0_prep1")[0]
        return p1_given_0, p0_given_1

    candidates = [q for q in range(backend.num_qubits) if props.is_qubit_operational(q)]
    qubit = min(candidates, key=lambda q: sum(readout(q)))
    p1_given_0, p0_given_1 = readout(qubit)

    # A perfect H gives 0.5/0.5; readout error then moves probability between the outcomes.
    p_tails = 0.5 * (1 - p0_given_1) + 0.5 * p1_given_0
    prediction = {
        "written_at": now(),
        "model": "ideal H, then the qubit's calibrated readout confusion; gate error and "
        "decay before measurement ignored (absorbed into readout calibration)",
        "qubit": qubit,
        "prob_meas1_prep0": p1_given_0,
        "prob_meas0_prep1": p0_given_1,
        "p_tails": p_tails,
        "shots": SHOTS,
        "expected_tails": p_tails * SHOTS,
        "sigma_tails": math.sqrt(SHOTS * p_tails * (1 - p_tails)),
    }
    write_json(out / "prediction.json", prediction)
    (out / "circuit.qasm").write_text(COIN_QASM)
    shutil.copy(__file__, out / "submit.py")

    circuit = qasm3.loads(COIN_QASM)
    isa = transpile(circuit, backend=backend, initial_layout=[qubit], optimization_level=0)
    ops = dict(isa.count_ops())
    print(f"qubit {qubit}: P(1|0)={p1_given_0:.4f} P(0|1)={p0_given_1:.4f}")
    print(f"predicted tails {p_tails:.4f} → {prediction['expected_tails']:.0f} ± "
          f"{prediction['sigma_tails']:.0f} of {SHOTS}")
    print(f"transpiled ops: {ops}")
    if not submit:
        print("dry run: nothing submitted")
        return

    submitted_at = now()
    job = SamplerV2(mode=backend).run([isa], shots=SHOTS)
    print(f"submitted job {job.job_id()} at {submitted_at}")
    result = job.result()
    data = result[0].data.c
    counts = data.get_counts()
    bits = data.get_bitstrings()
    metrics = job.metrics()
    write_json(out / "counts.json", counts)
    (out / "memory.txt").write_text("".join(bits) + "\n")
    write_json(
        out / "meta.json",
        {
            "job_id": job.job_id(),
            "backend": backend_name,
            "qubit": qubit,
            "shots": SHOTS,
            "submitted_at": submitted_at,
            "finished_at": now(),
            "quantum_seconds": metrics.get("usage", {}).get("quantum_seconds"),
            "usage": metrics.get("usage"),
            "timestamps": metrics.get("timestamps"),
            "transpiled_ops": ops,
            "qiskit_ibm_runtime": runtime_version,
        },
    )
    print(f"counts {counts}")
    print(f"usage {metrics.get('usage')}")


if __name__ == "__main__":
    main()
