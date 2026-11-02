# Archived hardware runs

Calibrations drift daily, so a hardware run can never be repeated. The archive is the
experiment: every job that ran on IBM hardware is kept here, whole, and committed to git.
`coin.archive.load_run` reads a run directory into a typed `Run`; `coin.archive.write_run`
writes one.

## Archived runs are immutable

Nothing under `runs/` is ever edited, renamed, reformatted or deleted. If an analysis
disagrees with the data, fix the analysis. If the format changes, the loader learns to
read the old layout too. When a later record supersedes an earlier one (final usage
arrives after the result), the later record goes in its own file rather than into
the earlier one. `write_run` refuses to write into a directory that already exists.

## Layout

One directory per job: `runs/<UTC date of submission>-<job id>/`, for example
`runs/2026-11-01-dbjsk29ffo6c73baaosg/`.

| File | Required | Holds |
| --- | --- | --- |
| `meta.json` | yes | the job: id, backend, qubits, shots, times, library versions |
| `circuit.qasm` | yes | the OpenQASM 3 program as submitted, before transpilation |
| `counts.json` or `counts.json.gz` | yes | outcome → number of shots |
| `calibration.json.gz` | yes | the backend's calibration snapshot, gzipped JSON |
| `prediction.json` | yes, unless waived | the forecast, written before submission |
| `memory.txt` or `memory.txt.gz` | no | the outcome of every shot, in order |
| `prediction-dryrun.json` | no | the forecast from a rehearsal that submitted nothing |
| `submit.py` | no | the exact script that produced the run |
| `usage.json` | no | the final QPU usage, fetched after the job finished |
| `extraction.json` | no | for a harvest, how its batch was extracted, added once the batch is spent |

All JSON is UTF-8, indented by two spaces, keys sorted, with a trailing newline.
New timestamps are ISO-8601 in UTC with microseconds, such as
`2026-11-02T09:30:00.123456+00:00`. The first run used second resolution, which let its
prediction and its submission share a second.

Outcome strings follow Qiskit: bit strings with classical bit 0 rightmost. Outcome `0`
is heads and `1` is tails.

### `meta.json`

| Key | Type | Meaning |
| --- | --- | --- |
| `job_id` | string | IBM's job id |
| `backend` | string | the device, such as `ibm_marrakesh` |
| `qubits` | list of integers | the physical qubits used, in classical-bit order |
| `qubit` | integer | the first run's single qubit, before `qubits` existed |
| `shots` | integer | shots requested and returned |
| `submitted_at` | timestamp | when the job was handed to IBM |
| `finished_at` | timestamp | when the result was received |
| `quantum_seconds` | number or null | QPU time as reported at result time, often not yet final |
| `library_version` | string, optional | the `fairest-coin` version that wrote the run |
| `no_prediction_reason` | string, optional | present only when the run carries no prediction |

Any other key (IBM's own `timestamps`, `transpiled_ops`, `qiskit_ibm_runtime`, the
result-time `usage`) is kept as it was written and loads into `Run.extra`.

### Plain or gzipped

`counts` and `memory` may be stored plain or gzipped. Runs since 0068 write `counts.json.gz`
and `memory.txt.gz`: a whole-chip run has about 100,000 distinct 156-bit outcomes, which is
16 MB per file as text and about 2.4 MB gzipped. The loader reads either form, so earlier
runs stay exactly as they were archived. A run holding both forms of one file is refused.

### `counts.json`

An object from outcome string to count. Every outcome has the same width, and the counts
sum to `shots`.

### `calibration.json.gz`

The backend's `properties().to_dict()` at the time the prediction was made, as gzipped
JSON (about 1.4 MB raw, 60 KB compressed). It is written with a zero gzip timestamp, so
the same calibration always gives the same bytes.

### `prediction.json` and `prediction-dryrun.json`

An object whose one common key is `written_at`, a timestamp. Everything else belongs to
the model that made the forecast and should name it, for example `model`, `p_tails`,
`expected_tails` and `sigma_tails`. `written_at` must be strictly before
`meta.json`'s `submitted_at`; `write_run` refuses otherwise.

A run may go without a prediction only if its writer passed `allow_no_prediction=True`
and recorded why in `no_prediction_reason`. The loader then accepts the missing file.

### `memory.txt`

Every shot's outcome concatenated on one line, then a newline. Each outcome is as wide
as the keys of `counts.json`, so the line is `shots × width` characters, and the
outcomes tally exactly to `counts.json`.

### `usage.json`

The final usage record, fetched once IBM marks it complete. `Run.qpu_seconds` takes
`qpu_charge_time_seconds` from here when present, and falls back to `meta.json`'s
`quantum_seconds`. The first run shows why: at result time its usage still read
`pending` and `quantum_seconds` was null.

### `extraction.json`

Only on harvest runs, and only once the harvest's pool batch is spent. The archived shots
and the seed recorded here determine every bit of the batch. That lets anyone check the
flips it gave, and, before they are spent, would let anyone predict them. So the run is
committed with this file only after `coin pool` shows the batch empty.

It holds the batch's provenance as the pool recorded it:
- `batch`, `run`, `job_id`, `backend`, `qubit`, `shots`;
- `entropy_per_bit` (the min-entropy per shot spent) and `estimate` (the estimate it was
  half of);
- `epsilon`, `input_bits` and `bits` (the batch's length);
- `seed` (hex, packed bits) and `seed_bits`;
- `added_at`, and `spent_before_publishing`.

`coin.extract.toeplitz` of the run's shots with that seed reproduces the batch bit for bit.
