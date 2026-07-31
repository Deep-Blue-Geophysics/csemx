# csemx — Python client

Reference reader, writer, and validator for
[csemx](https://github.com/Deep-Blue-Geophysics/csemx) bundles — an open,
vendor-neutral exchange format for modeling-ready frequency-domain
controlled-source electromagnetic (CSEM) data
([specification](https://deep-blue-geophysics.github.io/csemx/csemx-specification.html)).

The core (`read`/`write` and the dependency-light checks) needs **no
third-party packages**; the optional `full` extra adds the libraries required
for complete conformance validation.

> **Beta.** The package version tracks the format version it implements:
> `csemx` 0.1.x reads and validates format 0.1 bundles exactly. During the
> 0.x beta, format minor versions may include breaking changes and the
> validator accepts only its own format version (spec §12).

## Contents

- `src/csemx/io.py` — `read()` / `write()` and the `CsemxBundle` / `Table` types
- `src/csemx/validation.py` — `validate()` and the bundle/manifest checks
- `src/csemx/cli.py` — the `csemx` command-line entry point
- `src/csemx/schemas/` — bundled manifest schema and validator metadata
- `tests/` — validator regression tests

## Install

```bash
python3 -m pip install csemx            # core: read/write + light checks
python3 -m pip install "csemx[full]"    # + PyYAML, jsonschema, pyproj, pyarrow
```

From a repository checkout, editable:

```bash
python3 -m pip install -e "./python"
python3 -m pip install -e "./python[full]"
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
