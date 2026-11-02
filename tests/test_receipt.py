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
TYPES = {"string": str, "integer": int, "number": (int, float), "object": dict}


def validate(value: Any, schema: dict[str, Any]) -> list[str]:
    """The parts of JSON Schema the receipt schema uses: type, enum, required, properties,
    additionalProperties. Enough to hold the output to the document, without a dependency."""
    problems = []
    expected = TYPES[schema["type"]]
    if not isinstance(value, expected) or isinstance(value, bool):
        return [f"{value!r} is not {schema['type']}"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{value!r} not in {schema['enum']}")
    if schema["type"] == "object":
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
