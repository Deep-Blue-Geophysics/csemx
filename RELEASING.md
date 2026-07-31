# Releasing csemx

The specification is the product; the Python package is tooling that
implements exactly one format version. One tag stream encodes both:

> **Tag `vX.Y.Z`** — `X.Y` is the format version the release defines,
> `Z` is the tooling patch level.

So `v0.1.0` releases format 0.1 with package 0.1.0; a validator bugfix later
is `v0.1.1` (format unchanged); a format change is `v0.2.0`. The invariant is
**package major.minor = the format version it implements**. During the 0.x
beta a package accepts only its own format version; from 1.0 on it accepts
any same-major bundle at or below its minor (spec §12).

## Dependency updates

Dependabot proposes GitHub Actions updates weekly. Patch and minor updates
auto-merge once the `ci-ok` check passes; major updates wait for manual
review. A `main`-branch ruleset requires `ci-ok` for pull requests;
repository admins bypass it, so direct pushes to `main` are unaffected.

## One-time setup (before the first publish)

1. **PyPI Trusted Publishing** — on pypi.org, add a "pending publisher" for
   project `csemx`: owner `Deep-Blue-Geophysics`, repository `csemx`,
   workflow `publish.yml`, environment `pypi`. No API token is needed; the
   workflow authenticates via OIDC.
2. **Zenodo DOI (recommended)** — log in to zenodo.org with GitHub, enable
   the `csemx` repository under GitHub settings there. Every subsequent
   GitHub Release is archived automatically and receives a DOI; Zenodo reads
   `CITATION.cff` for metadata.

## Release checklist

1. Update `CHANGELOG.md`: retitle the "(unreleased)" section to the version
   and date.
2. Bump `version` in `python/pyproject.toml` and `version`/`date-released`
   in `CITATION.cff` to match the tag.
3. If the spec changed, confirm the format version appears consistently:
   spec title and §12, `schemas/manifest.schema.json` (`const`), both
   validator-metadata copies, every example manifest, the template, and the
   quickstart excerpt.
4. Verify locally (CI runs the same checks):
   - `python -m unittest discover -s python/tests` — with and without the
     optional dependencies installed;
   - `tools/check_examples.sh --full`;
   - `python tools/rebuild_example_zip.py --check`.
5. Commit, push, and wait for CI to pass on `main`.
6. Tag and push: `git tag -a vX.Y.Z -m "csemx X.Y.Z"` then
   `git push origin vX.Y.Z`. The publish workflow builds the package,
   verifies the tag matches `pyproject.toml`, and uploads to PyPI.
7. Create the GitHub Release for the tag. Separate **format changes**
   (normative) from **tooling changes** in the notes; credit reviewers for
   community-review changes. Zenodo archives the release and mints the DOI.
8. Verify: `pip install csemx==X.Y.Z` in a clean venv, run
   `csemx validate` on an example bundle.
