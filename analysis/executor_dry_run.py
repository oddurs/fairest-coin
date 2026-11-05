"""Item 0066: what does the executor Sampler hand back, before we trust it with QPU time?

SamplerV2 is deprecated in favour of `qiskit_ibm_runtime.executor_sampler.Sampler`, whose
results are post-processed on the client. Its `dry_run=True` sends the job to IBM for
validation and returns schema-preserving mock data without running on a QPU: no QPU time is
spent. This maps the one-qubit coin exactly as the adapter does, submits it as a dry run with
the adapter's options, and prints what came back, so the switch is made against a seen shape.

    uv run --extra ibm python analysis/executor_dry_run.py [BACKEND] [QUBIT]

Needs QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE. Every error is scrubbed of both.
"""

import json
import sys
from typing import Any

from qiskit_ibm_runtime.executor_sampler import Sampler

from coin.circuit import Circuit
from coin.compile import lower, to_qasm
from coin.ibm import SAMPLER_OPTIONS, IBMTransport, _plain

SHOTS = 100


def describe(value: Any, depth: int = 0) -> list[str]:
    """Type names and public attributes, two levels deep: the shape, not the data."""
    pad = "  " * depth
    lines = [f"{pad}{type(value).__module__}.{type(value).__qualname__}"]
    if depth < 2:
        for name in sorted(n for n in dir(value) if not n.startswith("_")):
            attribute = getattr(value, name, None)
            if not callable(attribute):
                lines.append(f"{pad}  .{name}: {type(attribute).__qualname__}")
    return lines


def main() -> None:
    backend_name = sys.argv[1] if len(sys.argv) > 1 else "ibm_marrakesh"
    qubit = int(sys.argv[2]) if len(sys.argv) > 2 else 104
    transport = IBMTransport()
    try:
        qasm = to_qasm(lower(Circuit(1).h(0).measure(0, 0)))
        backend, isa, executed = transport._map(backend_name, qasm, [qubit])
        sampler = Sampler(mode=backend, options=SAMPLER_OPTIONS)
        final = sampler.finalize_options()
        print("finalized twirling:", final.twirling)
        print("finalized dynamical decoupling:", final.dynamical_decoupling)
        print("archived options would be:", json.dumps(_plain(sampler.options), sort_keys=True))
        print("executed ops:", executed)

        job = sampler.run([isa], shots=SHOTS, dry_run=True)
        print("job id:", job.job_id())
        result = job.result()
        print("result:")
        print("\n".join(describe(result)))
        # Typed loosely on purpose: the stubs allow a QuantumProgramItemResult here, which has
        # no .data. Which one arrives is the question this script answers.
        pub: Any = result[0]
        print("result[0]:")
        print("\n".join(describe(pub)))
        data = getattr(pub, "data", None)
        if data is None:
            print("result[0] has no .data: SamplerV2's result shape does not carry over")
        else:
            print("result[0].data:")
            print("\n".join(describe(data)))
            bits = data.c.get_bitstrings()
            print(f"result[0].data.c.get_bitstrings(): {len(bits)} strings, first {bits[:5]}")
        try:
            print("metrics usage:", job.metrics().get("usage"))
        except Exception as error:
            print("metrics failed:", transport._scrub(str(error)))
    except Exception as error:
        print(f"failed: {type(error).__name__}: {transport._scrub(str(error))}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
