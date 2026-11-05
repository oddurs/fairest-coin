"""One job, a different circuit each shot: the CHSH settings swept by parameter."""

import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from qiskit import qasm3
from qiskit.quantum_info import Operator

from coin import bell, chsh, cli
from coin.archive import load_run
from coin.circuit import Circuit, Gate
from coin.compile import sweep_qasm, to_qasm, zxzxz
from coin.gates import matrix
from coin.hardware import JobResult, Sweep, recover, submit
from coin.sim import probabilities
from tests.test_chsh import CALIBRATION, analytic_s
from tests.test_chsh import READOUT as CHSH_READOUT
from tests.test_compile import EXACT, distance_up_to_phase, unitary
from tests.test_hardware import NoFetch
from tests.test_harvest import cli_run
from tests.test_ibm import FakeService, credentials, heron_like  # noqa: F401 - credentials is a fixture

angles = st.floats(min_value=-4 * np.pi, max_value=4 * np.pi, allow_nan=False)


@given(angles, angles, angles)
def test_zxzxz_is_always_five_gates_and_the_same_unitary(a: float, b: float, c: float) -> None:
    u = (
        matrix(Gate("rz", (0,), (a,)))
        @ matrix(Gate("ry", (0,), (b,)))
        @ matrix(Gate("rz", (0,), (c,)))
    )
    gates = zxzxz(u, 0)
    assert [g.name for g in gates] == ["rz", "sx", "rz", "sx", "rz"]
    assert distance_up_to_phase(unitary(Circuit(1, tuple(gates))), u) < EXACT * 10


def test_the_four_settings_share_one_skeleton_and_mean_what_they_say() -> None:
    circuits = chsh.setting_circuits()
    for (i, j), native in circuits.items():
        ideal = chsh.circuit(chsh.ALICE[i], chsh.BOB[j])
        without = Circuit(2, tuple(op for op in ideal.ops if isinstance(op, Gate)))
        native_gates = Circuit(2, tuple(op for op in native.ops if isinstance(op, Gate)))
        assert distance_up_to_phase(unitary(native_gates), unitary(without)) < EXACT * 10
        e = chsh.correlation(probabilities(native))
        assert e == pytest.approx(math.cos(chsh.ALICE[i] - chsh.BOB[j]), abs=EXACT * 10)
    program = sweep_qasm([circuits[s] for s in chsh.SETTINGS])
    # Only the rz angles after the cz differ: three per qubit at most.
    assert 1 <= len(program.values[0]) <= 6


def test_a_swept_program_binds_to_each_circuit() -> None:
    circuits = [chsh.setting_circuits()[s] for s in chsh.SETTINGS]
    program = sweep_qasm(circuits)
    assert "input float[64] p0;" in program.qasm
    template = qasm3.loads(program.qasm)
    for circuit, row in zip(circuits, program.values, strict=True):
        bound = template.assign_parameters(dict(zip(template.parameters, row, strict=True)))
        bound.remove_final_measurements()
        without = Circuit(2, tuple(op for op in circuit.ops if isinstance(op, Gate)))
        assert distance_up_to_phase(np.asarray(Operator(bound).data), unitary(without)) < 1e-9


def test_circuits_that_differ_beyond_rz_angles_cannot_be_swept() -> None:
    with pytest.raises(ValueError, match="differing only in rz angles"):
        sweep_qasm([Circuit(1).rz(0.1, 0).sx(0), Circuit(1).rz(0.2, 0).x(0)])
    assert sweep_qasm([Circuit(1).rz(0.1, 0)]).values == ((),)


class SweepTransport:
    """Records the rows it was given, and reads back each row's own circuit's ideal bits."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rows: Sequence[Sequence[float]] | None = None
        self.rng = rng

    def calibration(self, backend: str) -> dict[str, Any]:
        return CALIBRATION

    def run(
        self,
        backend: str,
        qasm: str,
        layout: Sequence[int],
        shots: int,
        on_submitted: Callable[[str, dict[str, Any]], None] | None = None,
        *,
        parameter_values: Sequence[Sequence[float]] | None = None,
    ) -> JobResult:
        from datetime import UTC, datetime  # noqa: PLC0415

        assert parameter_values is not None
        assert len(parameter_values) == shots
        self.rows = parameter_values
        circuits = [chsh.setting_circuits()[s] for s in chsh.SETTINGS]
        program = sweep_qasm(circuits)
        memory = []
        for row in parameter_values:
            k = program.values.index(tuple(row))
            p = probabilities(circuits[k])
            outcomes = sorted(p)
            memory.append(str(self.rng.choice(outcomes, p=[p[o] for o in outcomes])))
        now = datetime.now(UTC)
        if on_submitted is not None:
            on_submitted("sweepjob1", {"submitted_at": now.isoformat()})
        return JobResult("sweepjob1", now, now, tuple(memory), 2.0, None, {}, {})


def test_a_sweep_sends_one_row_per_shot_and_archives_each_choice(tmp_path: Path) -> None:
    choices = tuple(np.random.default_rng(1).integers(0, 4, 2_000).tolist())
    chosen = bell.plan_chsh("fake", CALIBRATION, choices)
    transport = SweepTransport(np.random.default_rng(2))
    run = load_run(submit(transport, chosen.submission, tmp_path))
    assert chosen.submission.sweep is not None
    program = sweep_qasm(chosen.submission.sweep.circuits)
    assert transport.rows == [program.values[k] for k in choices]
    assert run.extra["choices"] == "".join(map(str, choices))
    assert "input float[64]" in run.circuit_qasm
    # The ideal pair's correlations come back through the archive: S near 2√2.
    result = chsh.estimate(chsh.counts_by_setting(run.memory or (), run.extra["choices"]))
    assert abs(result.s - chsh.TSIRELSON) < 4 * result.standard_error


def test_a_recovered_sweep_keeps_its_choices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    choices = (0, 1, 2, 3) * 25
    chosen = bell.plan_chsh("fake", CALIBRATION, choices)

    def interrupted(*_args: Any, **_kwargs: Any) -> Path:
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr("coin.hardware.write_run", interrupted)
        with pytest.raises(KeyboardInterrupt):
            submit(SweepTransport(np.random.default_rng(3)), chosen.submission, tmp_path)
    run = load_run(recover(NoFetch, "sweepjob1", tmp_path))
    assert run.extra["choices"] == "0123" * 25


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: replace(s, sweep=Sweep(s.sweep.circuits, (0,) * (s.shots - 1))), "per shot"),
        (lambda s: replace(s, sweep=Sweep(s.sweep.circuits, (4,) * s.shots)), "per shot"),
        (lambda s: replace(s, sweep=Sweep(s.sweep.circuits[1:], (0,) * s.shots)), "first circuit"),
    ],
    ids=["too few choices", "a choice out of range", "a sweep not led by the circuit"],
)
def test_a_malformed_sweep_is_refused_before_hardware(change: Any, message: str) -> None:
    chosen = bell.plan_chsh("fake", CALIBRATION, (0, 1, 2, 3))
    with pytest.raises(ValueError, match=message):
        change(chosen.submission)


def test_the_chsh_prediction_is_the_analytic_one_for_the_swept_circuits() -> None:
    # The fixture's sx gates are perfect, so the extra pulses of the swept form cost nothing
    # and the depolarizing-and-readout formula still holds.
    chosen = bell.plan_chsh("fake", CALIBRATION, (0, 1, 2, 3) * 100)
    assert chosen.pair == (2, 3)
    assert chosen.s == pytest.approx(analytic_s((2, 3), CHSH_READOUT), abs=1e-9)
    values = chosen.submission.prediction.values
    assert values["purpose"] == "chsh"
    assert values["rounds"] == 400


def test_coin_run_chsh_dry_run_and_submit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    transport = SweepTransport(np.random.default_rng(4))
    monkeypatch.setattr(cli, "_transport", lambda: transport)
    argv = ["run", "chsh", "--backend", "fake", "--rounds", "4000", "--runs-dir", str(tmp_path)]
    code, out, _ = cli_run([*argv, "--dry-run"], capsys)
    assert code == 0
    assert "pair         2-3" in out
    assert out.rstrip().endswith("dry run: nothing submitted")
    assert transport.rows is None
    code, out, err = cli_run([*argv, "--submit"], capsys)
    assert code == 0, err
    assert "S_low" in out
    (directory,) = tmp_path.iterdir()
    code, compared, _ = cli_run(["compare", str(directory)], capsys)
    assert code == 0
    assert compared.splitlines() == out.splitlines()[-len(compared.splitlines()) :]
    counts = chsh.counts_by_setting(
        load_run(directory).memory or (), load_run(directory).extra["choices"]
    )
    assert {sum(c.values()) for c in counts.values()} != {0}


def test_counts_by_setting_needs_one_choice_per_shot() -> None:
    with pytest.raises(ValueError, match="2 shots but 1 choices"):
        chsh.counts_by_setting(("00", "11"), "0")
    assert chsh.counts_by_setting(("00", "01"), "03") == {
        (0, 0): {"00": 1},
        (0, 1): {},
        (1, 0): {},
        (1, 1): {"01": 1},
    }


@pytest.mark.usefixtures("credentials")
def test_the_adapter_runs_a_sweep_locally_one_row_per_shot() -> None:
    from coin.ibm import IBMTransport  # noqa: PLC0415 - only this test needs Qiskit's side

    circuits = [chsh.setting_circuits()[s] for s in chsh.SETTINGS]
    program = sweep_qasm(circuits)
    choices = [0, 1, 2, 3] * 50
    rows = [program.values[k] for k in choices]
    transport = IBMTransport(lambda _t, _i: FakeService(heron_like(2)))
    result = transport.run("fake", program.qasm, [0, 1], len(rows), parameter_values=rows)
    assert len(result.memory) == 200
    assert set(result.memory) <= {"00", "01", "10", "11"}
    assert result.executed_ops["cz"] == 1
    assert to_qasm(circuits[0]) != program.qasm  # the template is not any one circuit
