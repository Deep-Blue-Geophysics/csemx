# Working on csemx

## Baseline and scope

Follow the [company baseline at 0ff06456](https://github.com/Deep-Blue-Geophysics/engineering-baseline/blob/0ff06456bcd029f7d0391c28ab2140ba10562478/BASELINE.md)
and [release contract at 9e9dfc8d](https://github.com/Deep-Blue-Geophysics/engineering-baseline/blob/9e9dfc8dd6542a7b67e706089d6f1b1cd843cc16/RELEASE.md).
Alexander James coordinates local adoption in [ENG-36](https://linear.app/deep-blue-geophysics/issue/ENG-36).
These instructions work without personal checkouts or installed agent skills.

The specification is the product; Python and MATLAB implement its exchange
contract. Read [the specification](csemx-specification.md), [rationale](csemx-rationale.md)
and [release rules](RELEASING.md) before changing that contract. Preserve frequency-domain,
modeling-ready scope, explicit sign/phase conventions, source normalization,
units, geometry, CRS and total/secondary-field semantics. Raw acquisition and
solver/inversion settings are outside this format.

Bundles, archive paths, manifests, CSV/Parquet tables and caller-provided objects
are untrusted input. Review path handling, resource use, numeric finiteness,
identifiers/references, geometry and write/overwrite behavior. Preserve validation
errors versus warnings and CLI exit semantics. A successful dependency-light
check does not establish full conformance or scientific adequacy.

## Setup and verification

Use Python >=3.9 and isolated virtual environments, never global pip installs.
From the repository root, create separate minimal and full environments (choose
unused paths if these exist):

```sh
python3 -m venv .venv/minimal
python3 -m venv .venv/full
.venv/full/bin/python -m pip install -r requirements-validation.txt build
.venv/minimal/bin/python -m unittest discover -s python/tests
PYTHON=.venv/minimal/bin/python tools/check_examples.sh
.venv/full/bin/python -m unittest discover -s python/tests
PYTHON=.venv/full/bin/python tools/check_examples.sh
PYTHON=.venv/full/bin/python tools/check_examples.sh --full
.venv/full/bin/python tools/rebuild_example_zip.py --check
.venv/full/bin/python -m build python
git diff --check
```

For iteration, run a focused unittest; delivery uses both dependency configurations
and package checks. Minimal mode intentionally skips optional-library tests and
Parquet examples; report counts and warnings. Full mode must have PyYAML,
jsonschema, pyproj and pyarrow. The fill-in template is intentionally skipped.
Record interpreter/platform and resolved dependency versions; requirements are
floors, not a reproducible lock. CI also exercises the Python floor and its upper
matrix version; one local interpreter does not cover that matrix.

Verify both wheel and sdist contain `schemas/manifest.schema.json` and
`schemas/csemx-validator-metadata.json`. Install the exact wheel into another
clean environment, change directory outside the checkout, and run its `csemx
validate` and `csemx inspect` commands against absolute example paths. Check
minimal and full installed configurations when qualifying a release. Checkout
tests inject the source path and cannot prove installed resource discovery.
[ENG-13](https://linear.app/deep-blue-geophysics/issue/ENG-13) owns clean-install
release qualification. MATLAB changes also need evidence using the affected
helpers; Python tests do not establish MATLAB compatibility.

## Contracts and review

Keep root and packaged schemas/validator metadata consistent. Follow the release
checklist for format-version changes across specification, examples, template,
quickstart and package metadata. Keep ZIP fixtures synchronized with unpacked
examples. Avoid regenerating scientific reference data merely to make tests pass.
Use independent expected conventions, values and malformed-input cases alongside
round trips; explain physical meaning and tolerance choices.

Use a focused branch and PR. Non-trivial changes need fresh-context review of
format compatibility, validation boundaries, scientific conventions and installed
consumer behavior. Update invalidated docs with the change. Handoff records the
issue, tested revision, commands/results/skips, toolchain, dependencies, artifact
identity and remaining gaps. Keep dated settings snapshots and inspection evidence
in the PR or ENG-36, linked from these instructions.

## Delivery and enforcement

Follow [RELEASING.md](RELEASING.md). Name the human driving each release as its
sole release owner and obtain explicit approval before tag push, publication or
consumer promotion. CI success and PR approval do not substitute for release
approval. Qualify the exact wheel/sdist and format version, verify published
identity through a clean install, and retain the prior compatible artifact and
recovery procedure. Never overwrite published versions or tags.

Tag pushes trigger PyPI publication; main pushes trigger Pages deployment.
Treat these side effects as part of delivery planning. Merge, published artifact
and verified downstream adoption are distinct completion stages.

Written requirements, executable workflows and configured required gates differ.
Inspect enabled workflows and effective branch rules before claiming enforcement;
record evidence in ENG-36 or its PR. `ci-ok` aggregates test and package jobs;
scientific adequacy, review and release approval still require human judgment.
No local exceptions are recorded here. Any exception needs scope, reason,
risk/compensation, owner, expiry/revisit trigger and required approval in Linear;
unavailable or skipped checks are not waivers.
