#!/usr/bin/env python3
"""Installed boundary probe; invoked with -I by check_distribution.py.

This deliberately does not add the checkout to sys.path or pass root schemas to
the validator. Detailed scientific regression coverage remains in python/tests.
"""
from __future__ import annotations

import csv
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

import csemx
import csemx.validation as validation


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    root = Path(sys.argv[1]).resolve()
    full = sys.argv[2] == "full"
    package = Path(csemx.__file__).resolve().parent
    require(Path(sys.prefix) in package.parents, f"Import escaped venv: {package}")
    require(root not in Path.cwd().parents and root != Path.cwd(), "Checkout cwd")
    print(f"PROBE Python {platform.python_version()} {platform.platform()} "
          f"csemx={importlib.metadata.version('csemx')} import={package}", flush=True)
    for module in ("yaml", "jsonschema", "pyproj", "pyarrow"):
        require((importlib.util.find_spec(module) is not None) == full,
                f"Unexpected dependency configuration: {module}")
    for path in (validation.DEFAULT_SCHEMA, validation.DEFAULT_MANIFEST_SCHEMA):
        require(path.parent == package / "schemas", f"Schema escaped package: {path}")
        require(path.read_bytes() == (root / "schemas" / path.name).read_bytes(),
                f"Installed schema differs: {path}")
    version = json.loads(validation.DEFAULT_SCHEMA.read_text())["format"]["version"]
    require(".".join(importlib.metadata.version("csemx").split(".")[:2]) == version,
            "Package/format version mismatch")
    cli = Path(sys.executable).parent / ("csemx.exe" if os.name == "nt" else "csemx")

    def command(expected, *args, diagnostic=None):
        result = subprocess.run([str(cli), *map(str, args)], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout, end="", flush=True)
        require(result.returncode == expected,
                f"CLI {args}: expected {expected}, got {result.returncode}")
        require("Traceback (most recent call last)" not in result.stdout,
                f"CLI crashed: {args}")
        if diagnostic is not None:
            require(diagnostic in result.stdout,
                    f"CLI {args}: missing diagnostic {diagnostic!r}")

    options = ["--full"] if full else []
    examples = root / "examples"
    for bundle in sorted(examples.glob("*.csemx")) + [examples / "example.csemx.zip"]:
        if bundle.name == "template.csemx":
            print("SKIP fill-in template", flush=True)
            continue
        if "mixed_parquet" in bundle.name and not full:
            print("SKIP Parquet in minimal environment", flush=True)
            continue
        errors, warnings = csemx.validate(bundle, full=full)
        require(not errors, f"{bundle}: {errors}")
        require(not full or not warnings, f"Full-validation warnings: {warnings}")
        require(csemx.read(bundle).tables["data"].rows, f"Empty fixture: {bundle}")
        command(0, "validate", bundle, *options)
    command(0, "inspect", examples / "example.csemx")
    if not full:
        command(1, "validate", examples / "example.csemx", "--full",
                diagnostic="full validation requires")

    with tempfile.TemporaryDirectory(prefix="rejected-") as temporary:
        work = Path(temporary)
        # Spec §12: beta versions are exact-match. Use an adjacent minor so this
        # tests version rejection independently of how YAML/schema are loaded.
        wrong_version = shutil.copytree(examples / "example.csemx", work / "version.csemx")
        manifest = wrong_version / "manifest.yaml"
        original = manifest.read_text()
        old = f'version: "{version}"'
        require(old in original, "Version mutation did not match fixture")
        major, minor = map(int, version.split("."))
        manifest.write_text(original.replace(old, f'version: "{major}.{minor + 1}"', 1))
        errors, _ = csemx.validate(wrong_version, full=full)
        require(any("not supported" in e for e in errors), str(errors))
        command(1, "validate", wrong_version, *options, diagnostic="not supported")

        # Spec §3.12: a negative frequency is invalid, irrespective of the
        # physically meaningful response amplitudes in the unchanged example.
        negative = shutil.copytree(examples / "example.csemx", work / "negative.csemx")
        data = negative / "data.csv"
        with data.open(newline="") as handle:
            reader = csv.DictReader(handle)
            columns, rows = reader.fieldnames, list(reader)
        rows[0]["frequency"] = "-1"
        with data.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        errors, _ = csemx.validate(negative, full=full)
        require(any("frequency must be >= 0" in e for e in errors), str(errors))
        command(1, "validate", negative, *options, diagnostic="frequency must be >= 0")
        missing = work / "missing.csemx"
        command(2, "validate", missing, *options, diagnostic="ERROR: unsupported bundle path:")
        command(2, "inspect", missing, diagnostic="ERROR: unsupported bundle path:")
        try:
            csemx.read(missing)
        except csemx.ValidationError:
            pass
        else:
            raise AssertionError("Missing input did not raise public ValidationError")
    print("PASS installed boundary checks", flush=True)


if __name__ == "__main__":
    main()
