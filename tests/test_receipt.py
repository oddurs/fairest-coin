import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from coin import cli, harvest
from coin.archive import load_run
from coin.pool import Pool, receipt
from tests.test_harvest import SHOTS, FakeTransport, calibration  # noqa: F401 - a fixture

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "docs" / "receipt.schema.json").read_text())
TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "object": dict,
    "array": list,
    "boolean": bool,
    "null": type(None),
}


def _is(value: Any, name: str) -> bool:
    # bool is an int in Python, but not in JSON.
    return isinstance(value, TYPES[name]) and (name == "boolean") == isinstance(value, bool)


def validate(value: Any, schema: dict[str, Any]) -> list[str]:
    """The parts of JSON Schema the receipt schema uses: type (one or a list), enum,
    required, properties, additionalProperties, items. Enough to hold the output to the
    document, without a dependency."""
    problems = []
    names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    if not any(_is(value, name) for name in names):
        return [f"{value!r} is not {schema['type']}"]
    if isinstance(value, list):
        for i, item in enumerate(value):
            problems += [f"[{i}]: {p}" for p in validate(item, schema["items"])]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{value!r} not in {schema['enum']}")
    if isinstance(value, dict):
        problems += [f"missing {k}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            problems += [f"unexpected {k}" for k in value if k not in schema["properties"]]
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                problems += [f"{k}: {p}" for p in validate(value[k], sub)]
    return problems


@pytest.fixture
def harvested(calibration: dict[str, Any], tmp_path: Path) -> Path:  # noqa: F811
    chosen = harvest.plan("ibm_marrakesh", calibration, SHOTS)
    runs = tmp_path / "runs"
    harvest.harvest(FakeTransport(calibration), chosen, runs, Pool(), submit_script="x")
    return runs


def flip(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    try:
        code = cli.main(["flip", *argv])
    except SystemExit as exit_info:
        code = int(exit_info.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def test_the_json_receipt_follows_the_documented_schema(
    harvested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = flip(["--json"], capsys)
    assert code == 0
    assert validate(json.loads(out), SCHEMA) == []


def test_the_validator_catches_what_the_schema_forbids() -> None:
    good = dict.fromkeys(SCHEMA["required"], 0)
    assert "unexpected extra" in validate({**good, "extra": 1}, SCHEMA)
    assert "missing run" in validate({k: v for k, v in good.items() if k != "run"}, SCHEMA)


def test_the_receipt_resolves_to_its_archived_run(
    harvested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = flip(["--json"], capsys)
    assert code == 0
    flip_ = json.loads(out)
    run = load_run(harvested / flip_["run"])
    assert run.job_id == flip_["job_id"]
    assert run.qubits == (flip_["qubit"],)
    assert run.backend == flip_["backend"]


def test_consecutive_flips_have_consecutive_offsets(
    harvested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offsets = [json.loads(flip(["--json"], capsys)[1])["offset"] for _ in range(3)]
    assert offsets == [0, 1, 2]


def test_quiet_prints_only_the_face(harvested: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = flip(["--quiet"], capsys)
    assert code == 0
    assert out in {"HEADS\n", "TAILS\n"}


def test_the_plain_receipt_names_the_run_and_the_job(
    harvested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = flip([], capsys)
    lines = out.splitlines()
    assert code == 0
    assert lines[0] in {"HEADS", "TAILS"}
    assert "job fakeharvest01" in lines[1]
    assert "bit 1 of" in lines[2]
    assert "Toeplitz extraction" in lines[3]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--json", "--shots", "5"], "describe one flip"),
        (["--quiet", "--shots", "5"], "describe one flip"),
        (["--sim", "--json"], "--sim has none"),
    ],
)
def test_receipt_flags_that_do_not_fit_are_usage_errors(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = flip(argv, capsys)
    assert code == 2
    assert message in err


def test_a_receipt_is_for_one_bit(tmp_path: Path) -> None:
    pool = Pool(tmp_path)
    pool.add([1, 0], {"run": "r"}, label="a")
    (draw,) = pool.take(2)
    with pytest.raises(ValueError, match="one flip"):
        receipt(draw, datetime.now(UTC))


def test_a_plain_receipt_says_it_is_not_certified(
    harvested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = flip(["--json"], capsys)
    assert code == 0
    assert json.loads(out)["certified"] is False
    assert "certificate" not in json.loads(out)
    code, out, _ = flip([], capsys)
    assert "not Bell-certified" in out


def certified_pool(tmp_path: Path) -> Path:
    """A pool holding one certified batch, from a CHSH run whose settings it supplied."""
    import numpy as np  # noqa: PLC0415

    from coin import certify  # noqa: PLC0415
    from tests.test_certify import chsh_run  # noqa: PLC0415
    from tests.test_sweep import SweepTransport  # noqa: PLC0415

    run_dir, pool = chsh_run(tmp_path, SweepTransport(np.random.default_rng(20)), 4000)
    certify.certify(run_dir, pool)
    return tmp_path / "pool"


def test_a_certified_receipt_carries_its_certificate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from coin import chsh  # noqa: PLC0415

    monkeypatch.setattr(chsh, "INTERVAL_DRAWS", 20)
    pool = certified_pool(tmp_path)
    code, out, err = flip(["--certified", "--json", "--pool", str(pool)], capsys)
    assert code == 0, err
    receipt_ = json.loads(out)
    assert validate(receipt_, SCHEMA) == []
    assert receipt_["certified"] is True
    assert receipt_["qubit"] is None
    certificate = receipt_["certificate"]
    assert certificate["qubits"] == [2, 3]
    assert certificate["s_low"] > 2
    assert certificate["settings_batches"]
    code, out, _ = flip(["--certified", "--pool", str(pool)], capsys)
    assert "Bell-certified: S = " in out
    assert "qubits 2, 3" in out


def test_plain_and_certified_bits_are_never_mixed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from coin import chsh  # noqa: PLC0415

    monkeypatch.setattr(chsh, "INTERVAL_DRAWS", 20)
    pool = certified_pool(tmp_path)
    # The only plain bits went to the run's settings; certified ones are kept apart.
    code, _, err = flip(["--pool", str(pool)], capsys)
    assert code == 1
    assert "0 unspent bit(s)" in err
    remaining = sum(b.remaining for b in Pool(pool).status() if b.provenance.get("certified"))
    code, _, _ = flip(["--certified", "--shots", str(remaining), "--pool", str(pool)], capsys)
    assert code == 0
    code, _, err = flip(["--certified", "--pool", str(pool)], capsys)
    assert code == 1
    assert "0 unspent certified bit(s), 1 needed; run `coin certify`" in err


def test_certified_is_for_pool_bits(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = flip(["--sim", "--certified"], capsys)
    assert code == 2
    assert "not --sim" in err
