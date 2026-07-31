#!/usr/bin/env python3
"""Rebuild or verify examples/example.csemx.zip from examples/example.csemx.

The zip is a committed artifact that must stay in sync with the unpacked
bundle directory. Run with no arguments to rebuild it; run with --check to
verify it matches (used by CI). Rebuilds are deterministic: entries are
written in sorted order with a fixed timestamp, so an unchanged bundle
produces a byte-identical zip.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "example.csemx"
TARGET = ROOT / "examples" / "example.csemx.zip"
ARCNAME = "example.csemx"
# Fixed timestamp (the zip format's epoch) keeps rebuilds deterministic.
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def bundle_files() -> list[Path]:
    return sorted(p for p in SOURCE.rglob("*") if p.is_file())


def arcname(path: Path) -> str:
    return f"{ARCNAME}/{path.relative_to(SOURCE).as_posix()}"


def rebuild() -> None:
    with zipfile.ZipFile(TARGET, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in bundle_files():
            info = zipfile.ZipInfo(arcname(path), date_time=FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(f"rebuilt {TARGET.relative_to(ROOT)} from {SOURCE.relative_to(ROOT)}")


def check() -> list[str]:
    if not TARGET.exists():
        return [f"missing {TARGET.relative_to(ROOT)}"]
    problems = []
    expected = {arcname(path): path for path in bundle_files()}
    with zipfile.ZipFile(TARGET) as archive:
        in_zip = {name for name in archive.namelist() if not name.endswith("/")}
        for name in sorted(in_zip - expected.keys()):
            problems.append(f"only in zip: {name}")
        for name in sorted(expected.keys() - in_zip):
            problems.append(f"missing from zip: {name}")
        for name in sorted(expected.keys() & in_zip):
            if archive.read(name) != expected[name].read_bytes():
                problems.append(f"content differs: {name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the zip matches the bundle directory instead of rebuilding",
    )
    args = parser.parse_args()

    if not args.check:
        rebuild()
        return 0

    problems = check()
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        print(
            "ERROR: examples/example.csemx.zip is out of sync with "
            "examples/example.csemx; run tools/rebuild_example_zip.py",
            file=sys.stderr,
        )
        return 1
    print(f"OK: {TARGET.relative_to(ROOT)} matches {SOURCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
