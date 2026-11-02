#!/usr/bin/env python3
"""Qualify one built wheel or sdist in clean minimal and full installations.

Run with the Python version to qualify. Only use artifacts from a trusted build:
installing an sdist executes its build backend. No archive is extracted here.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ("manifest.schema.json", "csemx-validator-metadata.json")


def check_resources(artifact):
    if artifact.name.endswith(".whl"):
        with zipfile.ZipFile(artifact) as archive:
            for name in SCHEMAS:
                member = "csemx/schemas/" + name
                if archive.namelist().count(member) != 1:
                    raise ValueError(f"Expected exactly one {member}")
                if archive.read(member) != (ROOT / "schemas" / name).read_bytes():
                    raise ValueError(f"Packaged schema differs: {name}")
    elif artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact) as archive:
            for name in SCHEMAS:
                matches = [m for m in archive.getmembers()
                           if m.name.endswith("/src/csemx/schemas/" + name)]
                if len(matches) != 1 or not matches[0].isfile():
                    raise ValueError(f"Expected exactly one regular schema: {name}")
                with archive.extractfile(matches[0]) as handle:
                    if handle.read() != (ROOT / "schemas" / name).read_bytes():
                        raise ValueError(f"Packaged schema differs: {name}")
    else:
        raise ValueError("Expected a .whl or .tar.gz distribution")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    artifact = args.artifact.resolve(strict=True)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    print(f"ARTIFACT {artifact.name} sha256={digest}", flush=True)
    check_resources(artifact)
    # Do not inherit import overrides into pip or the installed console script.
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    for mode in ("minimal", "full"):
        with tempfile.TemporaryDirectory(prefix="csemx-installed-") as temporary:
            work = Path(temporary).resolve()
            if ROOT == work or ROOT in work.parents:
                raise ValueError("Temporary directory must be outside the checkout")
            venv.EnvBuilder(with_pip=True).create(work / "venv")
            bindir = work / "venv" / ("Scripts" if os.name == "nt" else "bin")
            python = bindir / ("python.exe" if os.name == "nt" else "python")

            def run(*command):
                subprocess.run(command, cwd=work, env=env, check=True)

            requirement = str(artifact) + ("[full]" if mode == "full" else "")
            print(f"INSTALL {artifact.name} {mode}", flush=True)
            # Disable pip's wheel cache so an sdist is actually rebuilt each time.
            run(str(python), "-I", "-m", "pip", "install", "--verbose", "--no-cache-dir", requirement)
            run(str(python), "-I", "-m", "pip", "check")
            run(str(python), "-I", "-m", "pip", "freeze", "--all")
            run(str(python), "-I", str(ROOT / "tools" / "installed_smoke.py"),
                str(ROOT), mode)
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
        raise ValueError("Artifact changed during qualification")
    print(f"QUALIFIED {artifact.name} sha256={digest}", flush=True)


if __name__ == "__main__":
    main()
