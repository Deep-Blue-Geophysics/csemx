# csemx — Python client

Reference reader, writer, and validator for [csemx](../README.md) bundles. The
core (`read`/`write` and the dependency-light checks) needs **no third-party
packages**; the optional `full` extra adds the libraries required for complete
conformance validation. Paths below are relative to the repository root.

## Contents

- `src/csemx/io.py` — `read()` / `write()` and the `CsemxBundle` / `Table` types
- `src/csemx/validation.py` — `validate()` and the bundle/manifest checks
- `src/csemx/cli.py` — the `csemx` command-line entry point
- `src/csemx/schemas/` — bundled manifest schema and validator metadata
- `tests/` — validator regression tests

## Install

From a checkout, editable:

```bash
python3 -m pip install -e "./python"          # core: read/write + light checks
python3 -m pip install -e "./python[full]"    # + PyYAML, jsonschema, pyproj, pyarrow
```

The `full` extra enables manifest JSON-Schema validation, EPSG/CRS checks, and
Parquet tables. Requires Python ≥ 3.9.

## Command line

```bash
csemx validate examples/example.csemx              # dependency-light checks
csemx validate --full examples/example.csemx.zip   # full conformance
csemx inspect examples/example.csemx               # summarize a bundle
```

## Library

```python
import csemx

bundle = csemx.read("examples/example.csemx")          # -> CsemxBundle
errors, warnings = csemx.validate("examples/example.csemx", full=True)
csemx.write(bundle, "out.csemx.zip")                   # directory or .zip
```

Public API: `read`, `write`, `validate`, and the `CsemxBundle`, `Table`, and
`ValidationError` types.

## Tests

```bash
python3 -m unittest python.tests.test_validate   # from the repository root
```
