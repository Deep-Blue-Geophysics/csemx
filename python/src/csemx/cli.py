from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from . import io

validator = importlib.import_module("csemx.validation")


def add_validate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("bundle", type=Path, help="bundle directory or .csemx.zip archive")
    parser.add_argument("--schema", type=Path, default=validator.DEFAULT_SCHEMA)
    parser.add_argument(
        "--manifest-schema",
        type=Path,
        default=validator.DEFAULT_MANIFEST_SCHEMA,
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "require PyYAML, jsonschema, pyproj, and pyarrow for production "
            "conformance validation"
        ),
    )


def run_validate(args: argparse.Namespace) -> int:
    try:
        errors, warnings = validator.validate(
            args.bundle,
            args.schema,
            full=args.full,
            manifest_schema_path=args.manifest_schema,
        )
    except validator.ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"OK: {args.bundle}")
    return 0


def run_inspect(args: argparse.Namespace) -> int:
    try:
        bundle = io.read(args.bundle)
    except validator.ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    survey = bundle.manifest.get("survey", {})
    print(f"Bundle: {args.bundle}")
    if survey:
        name = survey.get("name", "")
        revision = survey.get("revision", "")
        print(f"Survey: {name} revision {revision}")
    for table_name in io.REQUIRED_TABLES:
        table = bundle.tables[table_name]
        print(f"{table_name}: {len(table.rows)} rows ({table.filename})")
    if bundle.notes is not None:
        print("notes.md: present")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="csemx")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate a csemx bundle")
    add_validate_args(validate_parser)
    validate_parser.set_defaults(func=run_validate)

    inspect_parser = subparsers.add_parser("inspect", help="summarize a csemx bundle")
    inspect_parser.add_argument(
        "bundle",
        type=Path,
        help="bundle directory or .csemx.zip archive",
    )
    inspect_parser.set_defaults(func=run_inspect)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
