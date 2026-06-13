# csemx

`csemx` is a draft, vendor-neutral exchange format for modeling-ready
frequency-domain controlled-source electromagnetic data.

A bundle carries calibrated, current-normalized response functions, explicit
transmitter and receiver geometry, coordinate metadata, and sign/phase
conventions. It is not a raw acquisition container, an MT format, or an
inversion/modeling settings file.

## Purpose

Frequency-domain CSEM data is still delivered in vendor- and project-specific
formats. Most are workable in isolation, but they differ in layout and in how
fully they specify the conventions a modeling code needs: sign convention and
phase reference, source-current normalization, geometry, orientation, polarity,
coordinate reference system, and units. Anyone combining deliveries then has to
support every format variant and resolve any convention left unstated.

`csemx` removes that divergence with a documented, vendor-neutral bundle. It
makes these conventions explicit and mandatory, and carries the calibrated,
current-normalized complex responses and geometry needed by forward modeling
and inversion codes.

The result is simpler on both sides: a contractor exports once, and every code
that supports `csemx` can read the delivery; a modeling or inversion code
implements one reader and can ingest any dataset delivered in the format. One
exporter per producer and one reader per code replace a matrix of bespoke
converters. Because a bundle is a self-describing ZIP archive of CSV or Parquet
tables with a human-readable manifest, the data remains inspectable long after
delivery.

Those same properties make `csemx` suitable as an archival format for final,
processed CSEM datasets in public or institutional data repositories. An archive
can preserve the modeling-ready response values, geometry, coordinate reference
system, units, and sign/phase conventions in one documented package, without
requiring future users to reverse-engineer a project-specific delivery format.
Raw instrument output, calibration internals, and inversion settings remain out
of scope.

## Status

Pre-circulation draft. The format is open for technical review and is not frozen
as v1.0.

## Documents

- [`csemx-specification.md`](csemx-specification.md) — normative draft
  specification.
- [`csemx-rationale.md`](csemx-rationale.md) — design rationale and tradeoffs.
- [`examples/README.md`](examples/README.md) — notes on the example bundles.

## Bundle At A Glance

A delivered bundle is a `.csemx.zip` archive containing one top-level directory:

```text
<bundle-name>/
├── manifest.yaml
├── tx.csv | tx.parquet
├── tx_vertices.csv | tx_vertices.parquet
├── rx.csv | rx.parquet
├── rx_vertices.csv | rx_vertices.parquet
├── data.csv | data.parquet
└── notes.md                              # optional; all other files required
```

Each required table is supplied exactly once, either as CSV or Parquet. The
specification defines the required columns, geometry conventions, units,
normalization, and validation rules.

By default `real`/`imag` carry the **total** field; a bundle may instead deliver
the **secondary** field (free-space primary removed) by declaring
`field.content: secondary`. The secondary is stored in the canonical `V/A`/`T/A`
unit, with the primary computed from the encoded geometry (§3.11).

## Validation

Validate the repository examples:

```bash
tools/check_examples.sh
```

Install the optional full-validation dependencies and run full checks:

```bash
python3 -m pip install -r requirements-validation.txt
tools/check_examples.sh --full
```

Validate a bundle directly:

```bash
python3 tools/validate_csemx.py examples/example.csemx
python3 tools/validate_csemx.py --full examples/example.csemx.zip
```

Use `PYTHON=/path/to/python tools/check_examples.sh --full` to choose a specific
Python environment.

Install the Python client utilities from a checkout:

```bash
python3 -m pip install -e "./python[full]"
csemx validate --full examples/example.csemx.zip
csemx inspect examples/example.csemx
```

MATLAB helpers live under `matlab/+csemx` and provide `csemx.read`,
`csemx.write`, and `csemx.validate`.

## Repository Layout

- `schemas/` — draft manifest schema and validator metadata.
- `python/` — Python client package, CLI, and tests.
- `matlab/` — MATLAB client helpers.
- `tools/` — compatibility wrappers and repository scripts.
- `examples/` — unpacked and archived example bundles.

## Feedback

`csemx` is a pre-circulation draft and the conventions are not frozen. Technical
review from people who acquire, process, and model CSEM data is exactly what
this stage is for, and you do not need to be a programmer to take part.
Draft comments are welcome through **July 31, 2026**; later comments will still
be tracked but may miss the first v1.0 candidate.

The most useful comments answer concrete questions:

- **Coverage** — can a bundle represent data from your acquisition system and
  receiver type? What can it not represent?
- **Missing metadata** — is anything you consider essential absent?
- **Conventions** — do the sign, phase, and Fourier-transform conventions match
  yours? (See [`csemx-specification.md`](csemx-specification.md).)
- **Geometry** — do the transmitter and receiver tables capture your
  configurations, including multi-segment dipoles?
- **Units and normalization** — are the units and current normalization
  unambiguous and what you would expect?
- **Adoption** — what would stop you from reading or writing this format in your
  own tools?

How to send it, easiest first:

- **Email** <csemx@deepbluegeophysics.com> — plain prose is fine; ask for a
  PDF if you would rather annotate one. Say so if you would prefer your
  comments stay private.
- **GitHub Issues** — for a specific defect or a single concrete change.
- **GitHub Discussions** — for open-ended design questions.
- **Pull request** — if you want to propose exact wording.

No GitHub account is needed; emailed comments reach the same backlog.

## License

MIT. See [`LICENSE`](LICENSE).
