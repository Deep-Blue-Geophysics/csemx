from __future__ import annotations

import csv
import importlib
import json
import math
import shutil
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

validator = importlib.import_module("csemx.validation")

REQUIRED_TABLES = ("tx", "tx_vertices", "rx", "rx_vertices", "data")


@dataclass
class Table:
    filename: str
    columns: list[str]
    rows: list[dict[str, Any]]


@dataclass
class CsemxBundle:
    manifest: dict[str, Any]
    tables: dict[str, Table]
    notes: str | None = None


def read(path: str | Path, schema_path: str | Path | None = None) -> CsemxBundle:
    """Read a csemx bundle directory or .zip archive into simple Python objects."""

    schema_file = Path(schema_path) if schema_path is not None else validator.DEFAULT_SCHEMA
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    bundle = validator.Bundle(Path(path))
    names = set(bundle.names())

    manifest = validator.parse_manifest(bundle.read_text("manifest.yaml"))
    tables: dict[str, Table] = {}
    formats = schema["bundle"]["table_formats"]
    for table_name in REQUIRED_TABLES:
        filename, columns, rows = validator.resolve_table(
            bundle,
            names,
            table_name,
            schema["tables"][table_name],
            formats,
        )
        tables[table_name] = Table(filename=filename, columns=columns, rows=rows)

    notes = bundle.read_text("notes.md") if "notes.md" in names else None
    return CsemxBundle(manifest=manifest, tables=tables, notes=notes)


def write(
    bundle: CsemxBundle,
    path: str | Path,
    *,
    overwrite: bool = False,
    root_name: str | None = None,
) -> None:
    """Write a csemx bundle as CSV tables, either unpacked or as .zip.

    The writer is intentionally conservative: it writes CSV tables only. Parquet
    readers remain supported by the validator and ``read``.
    """

    target = Path(path)
    if target.name.endswith(".zip"):
        _write_zip(bundle, target, overwrite=overwrite, root_name=root_name)
    else:
        _write_directory(bundle, target, overwrite=overwrite)


def _write_zip(
    bundle: CsemxBundle,
    target: Path,
    *,
    overwrite: bool,
    root_name: str | None,
) -> None:
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    bundle_name = root_name or target.name.removesuffix(".zip")
    if not validator.SAFE_ROOT_RE.fullmatch(bundle_name):
        raise ValueError(f"zip root name is not filesystem-safe: {bundle_name!r}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / bundle_name
        _write_directory(bundle, root, overwrite=False)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(root.iterdir()):
                archive.write(file_path, arcname=f"{bundle_name}/{file_path.name}")


def _write_directory(bundle: CsemxBundle, root: Path, *, overwrite: bool) -> None:
    if root.exists():
        if not overwrite and any(root.iterdir()):
            raise FileExistsError(root)
        if overwrite:
            shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    (root / "manifest.yaml").write_text(
        _dump_manifest(bundle.manifest),
        encoding="utf-8",
    )
    for table_name in REQUIRED_TABLES:
        _write_csv(root / f"{table_name}.csv", _coerce_table(bundle.tables[table_name]))
    if bundle.notes is not None:
        (root / "notes.md").write_text(bundle.notes, encoding="utf-8")


def _coerce_table(value: Table | Mapping[str, Any]) -> Table:
    if isinstance(value, Table):
        return value
    rows = list(value.get("rows", []))
    columns = list(value.get("columns", rows[0].keys() if rows else []))
    filename = str(value.get("filename", ""))
    return Table(filename=filename, columns=columns, rows=rows)


def _write_csv(path: Path, table: Table) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=table.columns)
        writer.writeheader()
        for row in table.rows:
            writer.writerow({column: _csv_cell(row.get(column, "")) for column in table.columns})


def _csv_cell(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return value


def _dump_manifest(manifest: Mapping[str, Any]) -> str:
    if validator.yaml is not None:
        return validator.yaml.safe_dump(manifest, sort_keys=False)
    return _dump_mapping(manifest)


def _dump_mapping(mapping: Mapping[str, Any], indent: int = 0) -> str:
    lines = []
    prefix = " " * indent
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            lines.append(f"{prefix}{key}:")
            lines.append(_dump_mapping(value, indent + 2).rstrip("\n"))
        else:
            lines.append(f"{prefix}{key}: {_dump_scalar(value)}")
    return "\n".join(lines) + "\n"


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ", ".join(_dump_scalar(item) for item in value) + "]"
    return json.dumps(str(value))
