#!/usr/bin/env python3
"""Draft csemx validator.

The default path keeps CSV table parsing and non-CRS checks dependency-light.
Use ``--full`` for conformance validation that requires PyYAML, jsonschema,
pyproj, and pyarrow.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

try:  # Optional; needed only for bundles that contain Parquet tables.
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - exercised only without pyarrow.
    pa = None
    pq = None

try:  # Optional in quick mode; required for full CRS validation.
    from pyproj import CRS
except ImportError:  # pragma: no cover - exercised only without pyproj.
    CRS = None

try:  # Optional; the fallback parser supports the repository manifests.
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML.
    yaml = None

try:  # Optional in quick mode; required for full manifest schema validation.
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only without jsonschema.
    Draft202012Validator = None


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]


def default_schema_path(filename: str) -> Path:
    """Find schemas in a source checkout first, then packaged data."""

    candidates = [
        REPO_ROOT / "schemas" / filename,
        PACKAGE_ROOT / "schemas" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


DEFAULT_SCHEMA = default_schema_path("csemx-validator-metadata.json")
DEFAULT_MANIFEST_SCHEMA = default_schema_path("manifest.schema.json")
SAFE_ROOT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
ACQUIRED_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
ACQUIRED_UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
# §3.13 time_utc: the §4 UTC grammar extended with optional 1-9 fractional
# digits and a leap-second seconds field.
TIME_UTC_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?Z"
)
# Non-exhaustive offline fast-path: common geographic CRS codes rejected for
# epsg_horizontal without pyproj. NOT a complete list of geographic CRSs — the
# authoritative projected-vs-geographic check is crs.is_projected (pyproj, used
# whenever available); this set only catches frequent cases when pyproj is absent.
GEOGRAPHIC_EPSG = {4267, 4269, 4326, 4258, 4979}
COINCIDENT_TOL_M = 1e-6
SEGMENT_TOL_M = 1e-6
CANONICAL_RX_COMPONENT_GEOMETRY = {
    "Ex": "wire",
    "Ey": "wire",
    "Ez": "wire",
    "Bx": "point",
    "By": "point",
    "Bz": "point",
}
NOTES_MAX_CHARS = 1024
PARQUET_STRING_COLUMNS = {
    "tx_station_id",
    "tx_component_id",
    "rx_station_id",
    "rx_component_id",
    "geometry_type",
    "notes",
    "group_kind",
    "group_id",
    "element_kind",
    "station_id",
    "component_id",
    "time_utc",
}
PARQUET_INTEGER_COLUMNS = {
    "vertex_index",
    "use",
    "sequence",
}
PARQUET_FLOAT_COLUMNS = {
    "azimuth_deg",
    "dip_deg",
    "point_moment_area_m2",
    "easting",
    "northing",
    "elev",
    "altitude",
    "frequency",
    "real",
    "imag",
    "err_real",
    "err_imag",
    "tx_fundamental",
    "nav_heading_deg",
    "nav_pitch_deg",
    "nav_roll_deg",
    "nav_heading_sd_deg",
    "nav_pitch_sd_deg",
    "nav_roll_sd_deg",
    "nav_pos_sd_m",
    "nav_elev_sd_m",
}

# Acquisition endpoints are quoted strings in the manifest, so the standard
# SafeLoader is used directly (an unquoted YAML date/timestamp would parse as a
# date object and fail the manifest schema's `type: string`).


class ValidationError(Exception):
    pass


class _CsvDataRows:
    """Unmaterialized CSV data rows used only by the validator hot path."""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text


def validate_full_dependencies(errors):
    if yaml is None:
        errors.append(
            "full validation requires PyYAML; install requirements-validation.txt"
        )
    if Draft202012Validator is None:
        errors.append(
            "full validation requires jsonschema for manifest schema validation; "
            "install requirements-validation.txt"
        )
    if CRS is None:
        errors.append(
            "full validation requires pyproj for complete EPSG CRS checks; "
            "install requirements-validation.txt"
        )
    if pa is None or pq is None:
        errors.append(
            "full validation requires pyarrow for Parquet table support; "
            "install requirements-validation.txt"
        )


class Bundle:
    def __init__(self, path: Path):
        self.path = path
        self._zip = None
        self._root = ""

        if path.is_dir():
            self.kind = "dir"
            if (path / "manifest.yaml").exists():
                self._root = ""
            else:
                children = [p for p in path.iterdir() if p.is_dir()]
                if len(children) == 1 and (children[0] / "manifest.yaml").exists():
                    self._root = children[0].name + "/"
                else:
                    self._root = ""
        elif zipfile.is_zipfile(path):
            self.kind = "zip"
            self._zip = zipfile.ZipFile(path)
            self._root = self._detect_archive_root(self._zip.namelist())
        else:
            raise ValidationError(f"unsupported bundle path: {path}")

    @staticmethod
    def _detect_archive_root(names):
        files = [name for name in names if not name.endswith("/")]
        if not files:
            raise ValidationError("zip archive is empty")

        roots = set()
        rootless = []
        for name in files:
            parts = name.split("/", 1)
            if len(parts) == 1:
                rootless.append(name)
            else:
                roots.add(parts[0])

        if rootless or len(roots) != 1:
            raise ValidationError("zip archive must contain exactly one top-level directory")

        root = next(iter(roots))
        if not SAFE_ROOT_RE.fullmatch(root):
            raise ValidationError(f"zip top-level directory is not filesystem-safe: {root!r}")
        return root + "/"

    def names(self):
        if self.kind == "dir":
            base = self.path / self._root
            return sorted(str(p.relative_to(base)) for p in base.rglob("*") if p.is_file())
        return sorted(
            name[len(self._root):]
            for name in self._zip.namelist()
            if name.startswith(self._root) and not name.endswith("/")
        )

    def read_bytes(self, name: str) -> bytes:
        full = self._root + name
        if self.kind == "dir":
            return (self.path / full).read_bytes()
        return self._zip.read(full)

    def read_text(self, name: str) -> str:
        return self.read_bytes(name).decode("utf-8")


def strip_comment(line: str) -> str:
    in_quote = False
    quote = ""
    for i, ch in enumerate(line):
        if ch in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote = ch
            elif quote == ch:
                in_quote = False
        elif ch == "#" and not in_quote:
            return line[:i]
    return line


def split_top_level_commas(value: str):
    parts = []
    start = 0
    depth = 0
    in_quote = False
    quote = ""
    for i, ch in enumerate(value):
        if ch in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote = ch
            elif quote == ch:
                in_quote = False
        elif not in_quote:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(value[start:i].strip())
                start = i + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def parse_inline_map(value: str):
    inner = value[1:-1].strip()
    result = {}
    if not inner:
        return result
    for item in split_top_level_commas(inner):
        if ":" not in item:
            raise ValidationError(f"manifest inline map item is not key: value: {item!r}")
        key, raw_value = item.split(":", 1)
        result[key.strip()] = parse_scalar(raw_value.strip())
    return result


def parse_scalar(value: str):
    value = value.strip()
    if not value:
        return {}
    if value.startswith("{") and value.endswith("}"):
        return parse_inline_map(value)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    if re.fullmatch(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?", value):
        return float(value)
    # Mirror PyYAML: an *unquoted* ISO date/timestamp is a date/datetime object,
    # not a string. Acquisition endpoints (§4) must be quoted strings, so this
    # makes the dependency-light fallback reject unquoted dates exactly as the
    # PyYAML path does. Quoted scalars returned above already stay strings.
    if ACQUIRED_DATE_RE.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return value
    if ACQUIRED_UTC_RE.fullmatch(value):
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return value
    return value


def parse_simple_yaml(text: str):
    """Parse the simple nested mapping style used by the reference manifests."""
    root = {}
    stack = [(-1, root)]
    for raw in text.splitlines():
        line = strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise ValidationError(f"manifest uses unsupported indentation: {raw!r}")
        key_value = line.strip().split(":", 1)
        if len(key_value) != 2:
            raise ValidationError(f"manifest line is not a mapping: {raw!r}")
        key, value = key_value[0].strip(), key_value[1].strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        parsed = parse_scalar(value)
        parent[key] = parsed
        if parsed == {}:
            stack.append((indent, parsed))
    return root


def parse_manifest(text: str):
    if yaml is not None:
        try:
            loaded = yaml.safe_load(text)
        except Exception as exc:
            raise ValidationError(f"manifest YAML parse error: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValidationError("manifest root must be a mapping")
        return loaded
    return parse_simple_yaml(text)


def duplicate_values(values):
    seen = set()
    duplicates = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def load_csv(bundle: Bundle, name: str, *, materialize_rows: bool = True):
    text = bundle.read_text(name)
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValidationError(f"{name}: missing header")
    duplicates = duplicate_values(reader.fieldnames)
    if duplicates:
        formatted = ", ".join(repr(value) for value in sorted(duplicates))
        raise ValidationError(f"{name}: duplicate header column(s): {formatted}")
    if not materialize_rows:
        return reader.fieldnames, _CsvDataRows(text)
    rows = list(reader)
    for i, row in enumerate(rows, start=2):
        if None in row:
            raise ValidationError(f"{name}:{i}: too many fields")
    return reader.fieldnames, rows


def is_parquet_string_type(data_type):
    if pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
        return True
    if pa.types.is_dictionary(data_type):
        return is_parquet_string_type(data_type.value_type)
    return False


def validate_parquet_schema(table, table_schema, label):
    errors = []
    allowed = set(table_schema["required_columns"]) | set(table_schema.get("optional_columns", []))
    prefixes = tuple(table_schema.get("extension_prefixes", []))
    for field in table.schema:
        column = field.name
        if column not in allowed and not (prefixes and column.startswith(prefixes)):
            continue
        if prefixes and column.startswith(prefixes):
            continue

        if column in PARQUET_STRING_COLUMNS:
            if not is_parquet_string_type(field.type):
                errors.append(f"{label}: column {column!r} must be a Parquet string")
        elif column in PARQUET_INTEGER_COLUMNS:
            if not pa.types.is_integer(field.type):
                errors.append(f"{label}: column {column!r} must be a Parquet integer")
        elif column in PARQUET_FLOAT_COLUMNS:
            if not pa.types.is_float64(field.type):
                errors.append(f"{label}: column {column!r} must be a Parquet double (float64)")
        else:
            errors.append(f"{label}: no Parquet type rule for column {column!r}")
    return errors


def load_parquet(bundle: Bundle, name: str, table_schema):
    if pa is None or pq is None:
        raise ValidationError(f"{name}: Parquet validation requires pyarrow")
    source = pa.BufferReader(bundle.read_bytes(name))
    table = pq.read_table(source)
    header = list(table.column_names)
    duplicates = duplicate_values(header)
    if duplicates:
        formatted = ", ".join(repr(value) for value in sorted(duplicates))
        raise ValidationError(f"{name}: duplicate column(s): {formatted}")
    type_errors = validate_parquet_schema(table, table_schema, name)
    if type_errors:
        raise ValidationError("; ".join(type_errors))
    rows = [{column: record.get(column) for column in header} for record in table.to_pylist()]
    return header, rows


def resolve_table(
    bundle: Bundle,
    names: set[str],
    table_name: str,
    table_schema,
    formats,
    *,
    materialize_csv_rows: bool = True,
):
    candidates = [f"{table_name}.{fmt}" for fmt in formats if f"{table_name}.{fmt}" in names]
    if len(candidates) != 1:
        choices = " or ".join(f"{table_name}.{fmt}" for fmt in formats)
        if not candidates:
            raise ValidationError(f"missing required table: {choices}")
        raise ValidationError(f"table must appear in exactly one format: {candidates}")
    filename = candidates[0]
    if filename.endswith(".csv"):
        header, rows = load_csv(
            bundle,
            filename,
            materialize_rows=materialize_csv_rows,
        )
    elif filename.endswith(".parquet"):
        header, rows = load_parquet(bundle, filename, table_schema)
    else:
        raise ValidationError(f"unsupported table format: {filename}")
    return filename, header, rows


def is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_nan_value(value) -> bool:
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, str):
        return value.lower() == "nan"
    return False


def row_value(row, column):
    return row.get(column)


def canonical_key_value(value, column):
    if column == "frequency":
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return value
        if math.isfinite(parsed):
            return parsed
    if column == "vertex_index":
        if isinstance(value, bool):
            return value
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return value
        if str(value).strip() in {str(parsed), f"{parsed}.0"} or isinstance(value, int):
            return parsed
    return value


def require_string(value, label, pattern, errors):
    if is_blank(value) or is_nan_value(value):
        errors.append(f"{label}: missing required string")
        return None
    if not isinstance(value, str):
        errors.append(f"{label}: must be a string")
        return None
    if not pattern.fullmatch(value):
        errors.append(f"{label}: invalid value {value!r}")
        return None
    return value


def parse_float_cell(value, label, errors, *, allow_nan=False):
    if is_blank(value):
        errors.append(f"{label}: missing numeric value")
        return None
    if isinstance(value, bool):
        errors.append(f"{label}: invalid float {value!r}")
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label}: invalid float {value!r}")
        return None
    if math.isnan(parsed):
        if allow_nan:
            return parsed
        errors.append(f"{label}: NaN is not allowed")
        return None
    if not math.isfinite(parsed):
        errors.append(f"{label}: must be finite")
        return None
    return parsed


def parse_int_cell(value, label, errors):
    if is_blank(value) or is_nan_value(value):
        errors.append(f"{label}: missing integer value")
        return None
    if isinstance(value, bool):
        errors.append(f"{label}: invalid integer {value!r}")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append(f"{label}: invalid integer {value!r}")
        return None
    if str(value).strip() not in {str(parsed), f"{parsed}.0"} and not isinstance(value, int):
        errors.append(f"{label}: invalid integer {value!r}")
        return None
    return parsed


def check_unique(rows, key, label, errors):
    # Blank normalization: an optional key column (e.g. groups.component_id) is
    # empty "" in CSV and null in Parquet; both mean the same absent value.
    seen = set()
    for i, row in enumerate(rows, start=2):
        value = tuple(
            None if is_blank(cell := row_value(row, col)) else canonical_key_value(cell, col)
            for col in key
        )
        if value in seen:
            errors.append(f"{label}:{i}: duplicate key {value}")
        seen.add(value)


def validate_table_columns(header, table_schema, label, errors):
    for column in table_schema["required_columns"]:
        if column not in header:
            errors.append(f"{label}: missing required column {column}")

    allowed = set(table_schema["required_columns"]) | set(table_schema.get("optional_columns", []))
    prefixes = tuple(table_schema.get("extension_prefixes", []))
    for column in header:
        if column in allowed or (prefixes and column.startswith(prefixes)):
            continue
        errors.append(
            f"{label}: unexpected column {column!r}; producer extensions must use ext_* columns"
        )


def manifest_mapping(manifest, key, errors):
    value = manifest.get(key)
    if isinstance(value, dict):
        return value
    errors.append(f"manifest {key} must be a mapping")
    return {}


def format_schema_error_path(path):
    parts = list(path)
    if not parts:
        return "manifest"

    label = "manifest"
    for part in parts:
        if isinstance(part, int):
            label += f"[{part}]"
        else:
            label += f".{part}"
    return label


def validate_manifest_schema(manifest, manifest_schema, errors):
    if Draft202012Validator is None:
        return

    try:
        Draft202012Validator.check_schema(manifest_schema)
        validator = Draft202012Validator(manifest_schema)
    except Exception as exc:
        raise ValidationError(f"manifest JSON Schema is invalid: {exc}") from exc

    schema_errors = sorted(
        validator.iter_errors(manifest),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    for error in schema_errors:
        errors.append(f"{format_schema_error_path(error.absolute_path)}: {error.message}")


def parse_acquired_endpoint(value, label, errors):
    if is_blank(value) or is_nan_value(value):
        errors.append(f"{label}: missing acquisition endpoint")
        return None
    if not isinstance(value, str):
        errors.append(
            f"{label}: must be a quoted string in YYYY-MM-DD or "
            "YYYY-MM-DDTHH:MM:SSZ form (an unquoted YAML date is parsed as a date "
            "object, not a string)"
        )
        return None

    if ACQUIRED_DATE_RE.fullmatch(value):
        try:
            return "date", date.fromisoformat(value)
        except ValueError as exc:
            errors.append(f"{label}: invalid acquisition date {value!r}: {exc}")
            return None

    if ACQUIRED_UTC_RE.fullmatch(value):
        try:
            return "utc", datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            errors.append(f"{label}: invalid UTC acquisition timestamp {value!r}: {exc}")
            return None

    errors.append(f"{label}: must be exactly YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ")
    return None


def validate_manifest(manifest, schema, errors, warnings):
    format_info = manifest_mapping(manifest, "format", errors)
    survey = manifest_mapping(manifest, "survey", errors)
    coordinate_system = manifest_mapping(manifest, "coordinate_system", errors)
    elevation = manifest_mapping(manifest, "elevation", errors)
    sign = manifest_mapping(manifest, "sign", errors)

    if format_info.get("name") != schema["format"]["name"]:
        errors.append("manifest format.name must be csemx")
    validate_format_version(format_info.get("version"), schema["format"]["version"], errors)
    if manifest.get("domain") not in schema["enums"]["domain"]:
        errors.append("manifest domain must be frequency")
    if sign.get("time_dependence") not in schema["enums"]["time_dependence"]:
        errors.append("manifest sign.time_dependence is invalid")

    field = manifest.get("field")
    if field is not None:
        content = field.get("content") if isinstance(field, dict) else None
        if content not in schema["enums"]["field_content"]:
            errors.append("manifest field.content must be total or secondary")

    for key in (
        "name",
        "revision",
        "acquired_start",
        "acquired_end",
        "contractor",
        "contractor_reference",
    ):
        if key not in survey or is_blank(survey.get(key)):
            errors.append(f"manifest survey.{key} is required")
    revision = survey.get("revision")
    if revision is not None:
        parsed_revision = parse_int_cell(revision, "manifest survey.revision", errors)
        if parsed_revision is not None and parsed_revision < 1:
            errors.append("manifest survey.revision must be >= 1")
    acquired_start = parse_acquired_endpoint(
        survey.get("acquired_start"), "manifest survey.acquired_start", errors
    )
    acquired_end = parse_acquired_endpoint(
        survey.get("acquired_end"), "manifest survey.acquired_end", errors
    )
    if acquired_start is not None and acquired_end is not None:
        start_kind, start_value = acquired_start
        end_kind, end_value = acquired_end
        if start_kind != end_kind:
            errors.append(
                "manifest survey.acquired_start and acquired_end must both be dates or both be UTC timestamps"
            )
        elif end_value < start_value:
            errors.append("manifest survey.acquired_end must be on or after acquired_start")

    horizontal = coordinate_system.get("epsg_horizontal")
    vertical = elevation.get("epsg_vertical")
    validate_horizontal_epsg(horizontal, errors, warnings)
    validate_vertical_epsg(vertical, errors, warnings)


def parse_version(value, label, errors):
    if not isinstance(value, str):
        errors.append(f"{label} must be canonical MAJOR.MINOR string")
        return None
    version = str(value)
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)", version)
    if not match:
        errors.append(f"{label} must be canonical MAJOR.MINOR")
        return None
    return int(match.group(1)), int(match.group(2))


def validate_format_version(value, supported_version, errors):
    # Reader compatibility follows spec §12: during the 0.x beta only the exact
    # supported version is accepted (0.x minors may break); from 1.0 on, older
    # minors of the same major are accepted. With v0.1 metadata this accepts
    # only 0.1.
    parsed = parse_version(value, "manifest format.version", errors)
    supported = parse_version(supported_version, "validator format.version", errors)
    if parsed is None or supported is None:
        return
    major, minor = parsed
    supported_major, supported_minor = supported
    if supported_major == 0:
        compatible = (major, minor) == (supported_major, supported_minor)
    else:
        compatible = major == supported_major and minor <= supported_minor
    if not compatible:
        errors.append(
            f"manifest format.version {major}.{minor} is not supported by validator {supported_major}.{supported_minor}"
        )


def validate_horizontal_epsg(value, errors, warnings):
    parsed = parse_int_cell(value, "manifest coordinate_system.epsg_horizontal", errors)
    if parsed is None:
        return
    if parsed in GEOGRAPHIC_EPSG:
        errors.append("manifest coordinate_system.epsg_horizontal must be projected, not geographic")
        return
    if CRS is None:
        warnings.append(
            "pyproj not installed; projected EPSG check is limited to common geographic CRS codes"
        )
        return
    try:
        crs = CRS.from_epsg(parsed)
    except Exception as exc:  # pragma: no cover - depends on pyproj.
        errors.append(f"manifest coordinate_system.epsg_horizontal is not a known EPSG code: {exc}")
        return
    if not crs.is_projected:
        errors.append("manifest coordinate_system.epsg_horizontal must be a projected CRS")
        return
    # Projected is necessary but not sufficient: §3.1 fixes the unit at meter, and
    # the §3.4 geometry checks assume it. A projected CRS in feet (e.g. a US State
    # Plane ftUS zone) is is_projected but would silently corrupt lengths and areas.
    if not all(axis.unit_name == "metre" for axis in crs.axis_info):
        errors.append("manifest coordinate_system.epsg_horizontal must use meter axis units")


def has_meter_height_axis(crs):
    return any(
        axis.direction.lower() == "up" and axis.unit_name == "metre"
        for axis in crs.axis_info
    )


def validate_vertical_epsg(value, errors, warnings):
    parsed = parse_int_cell(value, "manifest elevation.epsg_vertical", errors)
    if parsed is None:
        return
    if parsed == 4979:
        return
    if CRS is None:
        warnings.append("pyproj not installed; vertical EPSG check is limited")
        return
    try:
        crs = CRS.from_epsg(parsed)
    except Exception as exc:  # pragma: no cover - depends on pyproj.
        errors.append(f"manifest elevation.epsg_vertical is not a known EPSG code: {exc}")
        return
    if not (parsed == 4979 or crs.is_vertical or crs.is_compound):
        errors.append("manifest elevation.epsg_vertical must define a vertical coordinate")
        return
    if not has_meter_height_axis(crs):
        errors.append("manifest elevation.epsg_vertical must use a meter height axis")


def validate_altitude_rule(manifest, table_headers, schema, errors):
    has_altitude = any("altitude" in table_headers[name] for name in ("tx_vertices", "rx_vertices"))
    altitude = manifest.get("altitude")
    if has_altitude:
        reference = altitude.get("reference") if isinstance(altitude, dict) else None
        if reference not in schema["enums"]["altitude_reference"]:
            errors.append("manifest altitude.reference is required when altitude columns are present")
    elif altitude is not None:
        errors.append("manifest altitude must be absent when no vertex table includes altitude")


def validate_ids(row, label, id_columns, errors):
    for column in id_columns:
        pattern = COMPONENT_RE if column.endswith("_component_id") else ID_RE
        require_string(row.get(column), f"{label}:{column}", pattern, errors)


def validate_notes(row, label, errors):
    if "notes" not in row or is_blank(row.get("notes")):
        return
    value = row.get("notes")
    if not isinstance(value, str):
        errors.append(f"{label}:notes: must be a string")
    elif len(value) > NOTES_MAX_CHARS:
        errors.append(f"{label}:notes: must be at most {NOTES_MAX_CHARS} characters")


def validate_point_columns(label, row, is_tx, errors):
    geometry_type = row.get("geometry_type")
    is_point = geometry_type == "point"
    az = row.get("azimuth_deg", "")
    dip = row.get("dip_deg", "")
    area = row.get("point_moment_area_m2", "")

    if is_point:
        azimuth = parse_float_cell(az, f"{label}:azimuth_deg", errors)
        dip_value = parse_float_cell(dip, f"{label}:dip_deg", errors)
        if azimuth is not None and not (0 <= azimuth < 360):
            errors.append(f"{label}: azimuth_deg must be in [0, 360)")
        if dip_value is not None and not (-90 <= dip_value <= 90):
            errors.append(f"{label}: dip_deg must be in [-90, 90]")
    else:
        if not is_blank(az) or not is_blank(dip):
            errors.append(f"{label}: azimuth_deg/dip_deg must be blank for non-point geometry")

    if is_tx and is_point:
        area_value = parse_float_cell(area, f"{label}:point_moment_area_m2", errors)
        if area_value is not None and area_value <= 0:
            errors.append(f"{label}: point_moment_area_m2 must be > 0")
    elif not is_blank(area):
        errors.append(f"{label}: point_moment_area_m2 is only valid for point TX")


def validate_time_utc(value, label, errors):
    if not isinstance(value, str):
        errors.append(f"{label}: must be a string in YYYY-MM-DDTHH:MM:SS[.f]Z form")
        return
    match = TIME_UTC_RE.fullmatch(value)
    if match is None:
        errors.append(
            f"{label}: invalid value {value!r}; must be "
            "YYYY-MM-DDTHH:MM:SS[.fffffffff]Z (1-9 fractional digits, trailing Z, "
            "no numeric UTC offset)"
        )
        return
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    try:
        date(year, month, day)
    except ValueError as exc:
        errors.append(f"{label}: invalid calendar date in {value!r}: {exc}")
        return
    if hour > 23 or minute > 59:
        errors.append(f"{label}: invalid UTC clock time in {value!r}")
        return
    if second > 60:
        errors.append(f"{label}: invalid seconds field in {value!r}")
        return
    if second == 60 and not (hour == 23 and minute == 59):
        errors.append(
            f"{label}: leap second in {value!r} is only valid at 23:59:60Z"
        )


NAV_ATTITUDE_RANGES = {
    # column -> (low, high, low_inclusive, high_inclusive, description)
    "nav_heading_deg": (0.0, 360.0, True, False, "in [0, 360)"),
    "nav_pitch_deg": (-90.0, 90.0, True, True, "in [-90, 90]"),
    "nav_roll_deg": (-180.0, 180.0, False, True, "in (-180, 180]"),
}
NAV_UNCERTAINTY_COLUMNS = (
    "nav_heading_sd_deg",
    "nav_pitch_sd_deg",
    "nav_roll_sd_deg",
    "nav_pos_sd_m",
    "nav_elev_sd_m",
)
# Attitude uncertainties whose value column should accompany them; the position
# uncertainties qualify the vertices instead and may appear alone (§3.13).
NAV_UNCERTAINTY_VALUE_COLUMNS = {
    "nav_heading_sd_deg": "nav_heading_deg",
    "nav_pitch_sd_deg": "nav_pitch_deg",
    "nav_roll_sd_deg": "nav_roll_deg",
}


def validate_nav_columns(row, row_label, errors, warnings):
    for column, (low, high, low_inc, high_inc, description) in NAV_ATTITUDE_RANGES.items():
        value = row.get(column, "")
        if is_blank(value):
            continue
        parsed = parse_float_cell(value, f"{row_label}:{column}", errors)
        if parsed is None:
            continue
        above_low = parsed >= low if low_inc else parsed > low
        below_high = parsed <= high if high_inc else parsed < high
        if not (above_low and below_high):
            errors.append(f"{row_label}: {column} must be {description}")

    for column in NAV_UNCERTAINTY_COLUMNS:
        value = row.get(column, "")
        if is_blank(value):
            continue
        parsed = parse_float_cell(value, f"{row_label}:{column}", errors)
        if parsed is not None and parsed < 0:
            errors.append(f"{row_label}: {column} must be >= 0")
        value_column = NAV_UNCERTAINTY_VALUE_COLUMNS.get(column)
        if value_column is not None and is_blank(row.get(value_column, "")):
            warnings.append(
                f"{row_label}: {column} is populated but {value_column} is blank"
            )

    time_utc = row.get("time_utc", "")
    if not is_blank(time_utc):
        validate_time_utc(time_utc, f"{row_label}:time_utc", errors)


def group_vertices(rows, key_columns, valid_keys, label, errors):
    grouped = {}
    for i, row in enumerate(rows, start=2):
        row_label = f"{label}:{i}"
        validate_ids(row, row_label, key_columns, errors)
        key = tuple(row.get(col) for col in key_columns)
        if key not in valid_keys:
            errors.append(f"{row_label}: unresolved key {key}")
        idx = parse_int_cell(row.get("vertex_index"), f"{row_label}:vertex_index", errors)
        easting = parse_float_cell(row.get("easting"), f"{row_label}:easting", errors)
        northing = parse_float_cell(row.get("northing"), f"{row_label}:northing", errors)
        elev = parse_float_cell(row.get("elev"), f"{row_label}:elev", errors)
        if "altitude" in row and not is_blank(row.get("altitude")):
            parse_float_cell(row.get("altitude"), f"{row_label}:altitude", errors)
        if idx is not None and easting is not None and northing is not None and elev is not None:
            grouped.setdefault(key, []).append((idx, easting, northing, elev))
    return grouped


def distance(a, b):
    return math.sqrt((a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2 + (a[3] - b[3]) ** 2)


def vector(vertex):
    return vertex[1], vertex[2], vertex[3]


def subtract(a, b):
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def add_scaled(a, scale, b):
    return a[0] + scale * b[0], a[1] + scale * b[1], a[2] + scale * b[2]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a):
    return math.sqrt(dot(a, a))


def clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))


def point_segment_distance(point, start, end):
    segment = subtract(end, start)
    length_sq = dot(segment, segment)
    if length_sq <= 0.0:
        return norm(subtract(point, start))
    t = clamp(dot(subtract(point, start), segment) / length_sq)
    projection = add_scaled(start, t, segment)
    return norm(subtract(point, projection))


def segment_distance(a0, a1, b0, b1):
    u = subtract(a1, a0)
    v = subtract(b1, b0)
    w = subtract(a0, b0)
    aa = dot(u, u)
    cc = dot(v, v)

    if aa <= 0.0 and cc <= 0.0:
        return norm(subtract(a0, b0))
    if aa <= 0.0:
        return point_segment_distance(a0, b0, b1)
    if cc <= 0.0:
        return point_segment_distance(b0, a0, a1)

    bb = dot(u, v)
    dd = dot(u, w)
    ee = dot(v, w)
    denominator = aa * cc - bb * bb

    if denominator <= 0.0:
        s = 0.0
    else:
        s = clamp((bb * ee - cc * dd) / denominator)

    t = (bb * s + ee) / cc
    if t < 0.0:
        t = 0.0
        s = clamp(-dd / aa)
    elif t > 1.0:
        t = 1.0
        s = clamp((bb - dd) / aa)

    closest_a = add_scaled(a0, s, u)
    closest_b = add_scaled(b0, t, v)
    return norm(subtract(closest_a, closest_b))


def loop_segments(vertices):
    count = len(vertices)
    return [(i, (i + 1) % count) for i in range(count)]


def segments_share_vertex(segment_a, segment_b):
    return bool(set(segment_a) & set(segment_b))


def warn_loop_self_intersections(vertices_by_index, key, label, warnings):
    segments = loop_segments(vertices_by_index)
    for i, segment_a in enumerate(segments):
        a0_index, a1_index = segment_a
        a0 = vector(vertices_by_index[a0_index])
        a1 = vector(vertices_by_index[a1_index])
        for segment_b in segments[i + 1:]:
            if segments_share_vertex(segment_a, segment_b):
                continue
            b0_index, b1_index = segment_b
            b0 = vector(vertices_by_index[b0_index])
            b1 = vector(vertices_by_index[b1_index])
            if segment_distance(a0, a1, b0, b1) <= SEGMENT_TOL_M:
                warnings.append(
                    f"{label}: loop {key} self-intersects between segments "
                    f"{vertices_by_index[a0_index][0]}-{vertices_by_index[a1_index][0]} "
                    f"and {vertices_by_index[b0_index][0]}-{vertices_by_index[b1_index][0]}"
                )
                return


def validate_vertex_counts(grouped, parent_rows, label, errors, warnings):
    for key, parent in parent_rows.items():
        vertices = grouped.get(key, [])
        geometry = parent["geometry_type"]
        count = len(vertices)
        if not vertices:
            errors.append(f"{label}: missing vertices for {key}")
            continue
        vertices_by_index = sorted(vertices, key=lambda item: item[0])
        indexes = [item[0] for item in vertices_by_index]
        expected = list(range(0, count))
        if indexes != expected:
            errors.append(f"{label}: vertex indices for {key} must be contiguous from 0")
        if geometry == "point" and count != 1:
            errors.append(f"{label}: point {key} must have exactly 1 vertex")
        if geometry == "wire" and count < 2:
            errors.append(f"{label}: wire {key} must have at least 2 vertices")
        if geometry == "loop" and count < 3:
            errors.append(f"{label}: loop {key} must have at least 3 vertices")
        for prev, current in zip(vertices_by_index, vertices_by_index[1:]):
            if distance(prev, current) <= COINCIDENT_TOL_M:
                errors.append(f"{label}: consecutive vertices coincident for {key}")
        if (
            geometry == "loop"
            and count >= 2
            and distance(vertices_by_index[0], vertices_by_index[-1]) <= COINCIDENT_TOL_M
        ):
            errors.append(f"{label}: loop {key} repeats first vertex; closure is implicit")
        if geometry == "loop" and count >= 4:
            warn_loop_self_intersections(vertices_by_index, key, label, warnings)


def validate_data_row(row, row_label, tx_keys, rx_keys, errors):
    """Validate one data row; returns True when the row is DC (frequency = 0)."""

    validate_ids(row, row_label, ("tx_station_id", "tx_component_id", "rx_station_id", "rx_component_id"), errors)
    tx_key = (row.get("tx_station_id"), row.get("tx_component_id"))
    rx_key = (row.get("rx_station_id"), row.get("rx_component_id"))
    if tx_key not in tx_keys:
        errors.append(f"{row_label}: unresolved tx key {tx_key}")
    if rx_key not in rx_keys:
        errors.append(f"{row_label}: unresolved rx key {rx_key}")

    frequency = parse_float_cell(row.get("frequency"), f"{row_label}:frequency", errors)
    if frequency is not None and frequency < 0:
        errors.append(f"{row_label}: frequency must be >= 0")
    # -0.0 parses to a float that compares equal to 0.0, so it is DC (§3.12).
    is_dc = frequency is not None and frequency == 0

    tx_fundamental = row.get("tx_fundamental", "")
    if not is_blank(tx_fundamental):
        parsed = parse_float_cell(tx_fundamental, f"{row_label}:tx_fundamental", errors)
        if parsed is not None and parsed <= 0:
            errors.append(f"{row_label}: tx_fundamental must be > 0")

    use = row.get("use", "")
    if "use" in row:
        parsed_use = parse_int_cell(use, f"{row_label}:use", errors)
        if parsed_use is not None and parsed_use not in (0, 1):
            errors.append(f"{row_label}: use must be 0 or 1")

    values = {
        name: parse_float_cell(row.get(name), f"{row_label}:{name}", errors, allow_nan=True)
        for name in ("real", "imag", "err_real", "err_imag")
    }
    if any(value is None for value in values.values()):
        return is_dc

    datum_missing = math.isnan(values["real"]) and math.isnan(values["imag"])
    datum_mixed = math.isnan(values["real"]) != math.isnan(values["imag"])
    errors_missing = math.isnan(values["err_real"]) or math.isnan(values["err_imag"])

    if datum_mixed:
        errors.append(f"{row_label}: real and imag must be finite together or NaN together")
    elif datum_missing:
        if not (math.isnan(values["err_real"]) and math.isnan(values["err_imag"])):
            errors.append(f"{row_label}: missing datum requires NaN err_real and err_imag")
    else:
        if errors_missing:
            errors.append(f"{row_label}: present datum requires finite errors")
        elif values["err_real"] < 0 or values["err_imag"] < 0:
            errors.append(f"{row_label}: errors must be >= 0")
        if is_dc:
            # §3.12: a present DC datum is purely real (±0.0 both count as 0).
            if values["imag"] != 0:
                errors.append(
                    f"{row_label}: present DC datum (frequency = 0) requires imag = 0"
                )
            if not math.isnan(values["err_imag"]) and values["err_imag"] != 0:
                errors.append(
                    f"{row_label}: present DC datum (frequency = 0) requires err_imag = 0"
                )

    return is_dc


class _CsvDataScan:
    __slots__ = ("unique_errors", "row_errors", "has_dc")

    def __init__(self):
        self.unique_errors = []
        self.row_errors = []
        self.has_dc = False


def _csv_row_dict(header, row):
    """Reproduce DictReader's complete mapping for a short CSV record."""

    row_length = len(row)
    return {
        column: row[index] if index < row_length else None
        for index, column in enumerate(header)
    }


def _classify_csv_id(value, pattern):
    canonical = None if is_blank(value) else value
    valid = (
        isinstance(value, str)
        and value.strip() != ""
        and value.lower() != "nan"
        and pattern.fullmatch(value) is not None
    )
    return canonical, valid


def _classify_csv_frequency(value):
    if is_blank(value):
        return None, None, False
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return value, None, False
    if not math.isfinite(parsed):
        return value, parsed, False
    return parsed, parsed, parsed >= 0


def _valid_optional_positive_float(value):
    if is_blank(value):
        return True
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(parsed) and parsed > 0


def _valid_csv_use(value):
    if is_blank(value) or is_nan_value(value):
        return False
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return False
    return str(value).strip() == str(parsed) and parsed in (0, 1)


def _simple_csv_lines(text):
    if '"' in text:
        return None
    for marker in (
        "\v",
        "\f",
        "\x1c",
        "\x1d",
        "\x1e",
        "\x85",
        "\u2028",
        "\u2029",
    ):
        if marker in text:
            return None
    return text.splitlines()


def _materialize_csv_data_rows(table):
    reader = csv.DictReader(io.StringIO(table["rows"].text))
    rows = list(reader)
    label = table["filename"]
    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise ValidationError(f"{label}:{row_number}: too many fields")
    return rows


def _scan_csv_data_legacy(
    table,
    tx_keys,
    rx_keys,
    *,
    check_uniqueness,
    validate_rows,
):
    """Exact fallback for quoted CSV and noncanonical column layouts."""

    scan = _CsvDataScan()
    rows = _materialize_csv_data_rows(table)
    label = table["filename"]
    if check_uniqueness:
        check_unique_columns = (
            "tx_station_id",
            "tx_component_id",
            "rx_station_id",
            "rx_component_id",
            "frequency",
        )
        check_unique(rows, check_unique_columns, label, scan.unique_errors)
    if validate_rows:
        for row_number, row in enumerate(rows, start=2):
            if validate_data_row(
                row,
                f"{label}:{row_number}",
                tx_keys,
                rx_keys,
                scan.row_errors,
            ):
                scan.has_dc = True
    return scan


def _check_standard_csv_data_structure(table, lines):
    label = table["filename"]
    column_count = len(table["header"])
    row_number = 1
    for line in lines[1:]:
        if not line:
            continue
        row_number += 1
        if line.count(",") + 1 > column_count:
            raise ValidationError(f"{label}:{row_number}: too many fields")


def _scan_standard_csv_data_unique(table, lines):
    """Fast five-column uniqueness pass for ordinary writer output."""

    scan = _CsvDataScan()
    label = table["filename"]
    column_count = len(table["header"])
    missing = object()
    tx_station_cache = {}
    tx_component_cache = {}
    rx_station_cache = {}
    rx_component_cache = {}
    frequency_cache = {}
    frequencies_by_series = {}
    finite = math.isfinite
    row_number = 1

    for line in lines[1:]:
        if not line:
            continue
        row_number += 1
        row = line.split(",")
        row_length = len(row)
        if row_length > column_count:
            raise ValidationError(f"{label}:{row_number}: too many fields")
        if row_length < 5:
            tx_station_raw = row[0] if row_length > 0 else None
            tx_component_raw = row[1] if row_length > 1 else None
            rx_station_raw = row[2] if row_length > 2 else None
            rx_component_raw = row[3] if row_length > 3 else None
            frequency_raw = row[4] if row_length > 4 else None
        else:
            tx_station_raw = row[0]
            tx_component_raw = row[1]
            rx_station_raw = row[2]
            rx_component_raw = row[3]
            frequency_raw = row[4]

        tx_station = tx_station_cache.get(tx_station_raw, missing)
        if tx_station is missing:
            tx_station = None if is_blank(tx_station_raw) else tx_station_raw
            tx_station_cache[tx_station_raw] = tx_station
        tx_component = tx_component_cache.get(tx_component_raw, missing)
        if tx_component is missing:
            tx_component = None if is_blank(tx_component_raw) else tx_component_raw
            tx_component_cache[tx_component_raw] = tx_component
        rx_station = rx_station_cache.get(rx_station_raw, missing)
        if rx_station is missing:
            rx_station = None if is_blank(rx_station_raw) else rx_station_raw
            rx_station_cache[rx_station_raw] = rx_station
        rx_component = rx_component_cache.get(rx_component_raw, missing)
        if rx_component is missing:
            rx_component = None if is_blank(rx_component_raw) else rx_component_raw
            rx_component_cache[rx_component_raw] = rx_component

        series = (tx_station, tx_component, rx_station, rx_component)
        frequencies = frequencies_by_series.get(series)
        if frequencies is None:
            frequencies = set()
            frequencies_by_series[series] = frequencies

        canonical_frequency = frequency_cache.get(frequency_raw, missing)
        if canonical_frequency is missing:
            if is_blank(frequency_raw):
                canonical_frequency = None
            else:
                try:
                    parsed_frequency = float(frequency_raw)
                except (TypeError, ValueError):
                    canonical_frequency = frequency_raw
                else:
                    canonical_frequency = (
                        parsed_frequency
                        if finite(parsed_frequency)
                        else frequency_raw
                    )
            frequency_cache[frequency_raw] = canonical_frequency

        previous_count = len(frequencies)
        frequencies.add(canonical_frequency)
        if len(frequencies) == previous_count:
            key = series + (canonical_frequency,)
            scan.unique_errors.append(
                f"{label}:{row_number}: duplicate key {key}"
            )

    return scan


def _scan_standard_csv_data_rows(table, lines, tx_keys, rx_keys):
    """Validate ordinary data.csv rows without per-row dictionaries."""

    scan = _CsvDataScan()
    label = table["filename"]
    header = table["header"]
    indexes = {column: index for index, column in enumerate(header)}
    real_index = indexes["real"]
    imag_index = indexes["imag"]
    err_real_index = indexes["err_real"]
    err_imag_index = indexes["err_imag"]
    tx_fundamental_index = indexes.get("tx_fundamental", -1)
    use_index = indexes.get("use", -1)
    max_value_index = max(
        real_index,
        imag_index,
        err_real_index,
        err_imag_index,
    )
    column_count = len(header)
    missing = object()
    tx_station_cache = {}
    tx_component_cache = {}
    rx_station_cache = {}
    rx_component_cache = {}
    frequency_cache = {}
    tx_fundamental_cache = {}
    use_cache = {}
    frequencies_by_series = {}
    row_number = 1

    for line in lines[1:]:
        if not line:
            continue
        row_number += 1
        row = line.split(",")
        row_length = len(row)
        if row_length > column_count:
            raise ValidationError(f"{label}:{row_number}: too many fields")
        if row_length < 5:
            tx_station_raw = row[0] if row_length > 0 else None
            tx_component_raw = row[1] if row_length > 1 else None
            rx_station_raw = row[2] if row_length > 2 else None
            rx_component_raw = row[3] if row_length > 3 else None
            frequency_raw = row[4] if row_length > 4 else None
        else:
            tx_station_raw = row[0]
            tx_component_raw = row[1]
            rx_station_raw = row[2]
            rx_component_raw = row[3]
            frequency_raw = row[4]

        tx_station_info = tx_station_cache.get(tx_station_raw, missing)
        if tx_station_info is missing:
            tx_station_info = _classify_csv_id(tx_station_raw, ID_RE)
            tx_station_cache[tx_station_raw] = tx_station_info
        tx_component_info = tx_component_cache.get(tx_component_raw, missing)
        if tx_component_info is missing:
            tx_component_info = _classify_csv_id(
                tx_component_raw,
                COMPONENT_RE,
            )
            tx_component_cache[tx_component_raw] = tx_component_info
        rx_station_info = rx_station_cache.get(rx_station_raw, missing)
        if rx_station_info is missing:
            rx_station_info = _classify_csv_id(rx_station_raw, ID_RE)
            rx_station_cache[rx_station_raw] = rx_station_info
        rx_component_info = rx_component_cache.get(rx_component_raw, missing)
        if rx_component_info is missing:
            rx_component_info = _classify_csv_id(
                rx_component_raw,
                COMPONENT_RE,
            )
            rx_component_cache[rx_component_raw] = rx_component_info
        frequency_info = frequency_cache.get(frequency_raw, missing)
        if frequency_info is missing:
            frequency_info = _classify_csv_frequency(frequency_raw)
            frequency_cache[frequency_raw] = frequency_info

        tx_station, tx_station_valid = tx_station_info
        tx_component, tx_component_valid = tx_component_info
        rx_station, rx_station_valid = rx_station_info
        rx_component, rx_component_valid = rx_component_info
        canonical_frequency, frequency, frequency_valid = frequency_info

        series = (tx_station, tx_component, rx_station, rx_component)
        frequencies = frequencies_by_series.get(series)
        if frequencies is None:
            frequencies = set()
            frequencies_by_series[series] = frequencies
        previous_count = len(frequencies)
        frequencies.add(canonical_frequency)
        if len(frequencies) == previous_count:
            key = series + (canonical_frequency,)
            scan.unique_errors.append(
                f"{label}:{row_number}: duplicate key {key}"
            )

        row_is_valid = (
            tx_station_valid
            and tx_component_valid
            and rx_station_valid
            and rx_component_valid
            and (tx_station_raw, tx_component_raw) in tx_keys
            and (rx_station_raw, rx_component_raw) in rx_keys
            and frequency_valid
        )

        if tx_fundamental_index >= 0:
            tx_fundamental_raw = (
                row[tx_fundamental_index]
                if tx_fundamental_index < row_length
                else None
            )
            tx_fundamental_valid = tx_fundamental_cache.get(
                tx_fundamental_raw,
                missing,
            )
            if tx_fundamental_valid is missing:
                tx_fundamental_valid = _valid_optional_positive_float(
                    tx_fundamental_raw
                )
                tx_fundamental_cache[tx_fundamental_raw] = (
                    tx_fundamental_valid
                )
            row_is_valid = row_is_valid and tx_fundamental_valid

        if use_index >= 0:
            use_raw = row[use_index] if use_index < row_length else None
            use_valid = use_cache.get(use_raw, missing)
            if use_valid is missing:
                use_valid = _valid_csv_use(use_raw)
                use_cache[use_raw] = use_valid
            row_is_valid = row_is_valid and use_valid

        if row_length > max_value_index:
            real_raw = row[real_index]
            imag_raw = row[imag_index]
            err_real_raw = row[err_real_index]
            err_imag_raw = row[err_imag_index]
        else:
            real_raw = row[real_index] if real_index < row_length else None
            imag_raw = row[imag_index] if imag_index < row_length else None
            err_real_raw = (
                row[err_real_index] if err_real_index < row_length else None
            )
            err_imag_raw = (
                row[err_imag_index] if err_imag_index < row_length else None
            )

        try:
            real = float(real_raw)
            imag = float(imag_raw)
            err_real = float(err_real_raw)
            err_imag = float(err_imag_raw)
        except (TypeError, ValueError):
            row_is_valid = False
        else:
            if any(
                math.isinf(value)
                for value in (real, imag, err_real, err_imag)
            ):
                row_is_valid = False
            else:
                real_missing = math.isnan(real)
                imag_missing = math.isnan(imag)
                err_real_missing = math.isnan(err_real)
                err_imag_missing = math.isnan(err_imag)
                if real_missing != imag_missing:
                    row_is_valid = False
                elif real_missing:
                    row_is_valid = (
                        row_is_valid
                        and err_real_missing
                        and err_imag_missing
                    )
                else:
                    row_is_valid = (
                        row_is_valid
                        and not err_real_missing
                        and not err_imag_missing
                        and err_real >= 0
                        and err_imag >= 0
                    )
                    if frequency == 0:
                        row_is_valid = (
                            row_is_valid
                            and imag == 0
                            and err_imag == 0
                        )

        if row_is_valid:
            if frequency == 0:
                scan.has_dc = True
            continue

        row_mapping = _csv_row_dict(header, row)
        if validate_data_row(
            row_mapping,
            f"{label}:{row_number}",
            tx_keys,
            rx_keys,
            scan.row_errors,
        ):
            scan.has_dc = True

    return scan


def _scan_csv_data(
    table,
    tx_keys=None,
    rx_keys=None,
    *,
    check_unique=True,
    validate_rows=False,
):
    """Scan data.csv while preserving the validator's diagnostic phases."""

    header = table["header"]
    lines = _simple_csv_lines(table["rows"].text)
    standard_key_order = header[:5] == [
        "tx_station_id",
        "tx_component_id",
        "rx_station_id",
        "rx_component_id",
        "frequency",
    ]
    required_values_present = all(
        column in header
        for column in ("real", "imag", "err_real", "err_imag")
    )
    if (
        lines is None
        or not standard_key_order
        or (validate_rows and not required_values_present)
    ):
        return _scan_csv_data_legacy(
            table,
            tx_keys,
            rx_keys,
            check_uniqueness=check_unique,
            validate_rows=validate_rows,
        )
    if validate_rows:
        return _scan_standard_csv_data_rows(
            table,
            lines,
            tx_keys,
            rx_keys,
        )
    if check_unique:
        return _scan_standard_csv_data_unique(table, lines)
    _check_standard_csv_data_structure(table, lines)
    return _CsvDataScan()


def validate_groups(table, schema, tx_keys, rx_keys, errors, warnings):
    label = table["filename"]
    station_ids = {
        "tx": {key[0] for key in tx_keys},
        "rx": {key[0] for key in rx_keys},
    }
    element_keys = {"tx": tx_keys, "rx": rx_keys}
    station_wide = set()  # (group_kind, group_id, element_kind, station_id)
    component_scoped = set()
    sequences = {}  # (group_kind, group_id, element_kind) -> {sequence: row number}

    for i, row in enumerate(table["rows"], start=2):
        row_label = f"{label}:{i}"
        kind = require_string(row.get("group_kind"), f"{row_label}:group_kind", COMPONENT_RE, errors)
        group_id = require_string(row.get("group_id"), f"{row_label}:group_id", ID_RE, errors)
        element_kind = row.get("element_kind")
        if element_kind not in schema["enums"]["element_kind"]:
            errors.append(f"{row_label}: element_kind must be tx or rx")
            element_kind = None
        station = require_string(row.get("station_id"), f"{row_label}:station_id", ID_RE, errors)
        component = row.get("component_id", "")
        validate_notes(row, row_label, errors)

        if element_kind is not None and station is not None:
            if station not in station_ids[element_kind]:
                errors.append(
                    f"{row_label}: unresolved station_id {station!r} for element_kind {element_kind}"
                )
            membership = (kind, group_id, element_kind, station)
            if is_blank(component):
                station_wide.add(membership)
            else:
                resolved = require_string(
                    component, f"{row_label}:component_id", COMPONENT_RE, errors
                )
                # A populated component that does not resolve jointly with its
                # station is an error, not a warning (§10).
                if resolved is not None and (station, resolved) not in element_keys[element_kind]:
                    errors.append(
                        f"{row_label}: unresolved component_id {resolved!r} for "
                        f"station_id {station!r} ({element_kind})"
                    )
                component_scoped.add(membership)

        sequence = row.get("sequence", "")
        if not is_blank(sequence):
            parsed = parse_int_cell(sequence, f"{row_label}:sequence", errors)
            if parsed is not None:
                if parsed < 0:
                    errors.append(f"{row_label}: sequence must be a nonnegative integer")
                if kind is not None and kind != "line":
                    warnings.append(
                        f"{row_label}: sequence is defined for group_kind=line, "
                        f"not {kind!r}"
                    )
                ordering = sequences.setdefault((kind, group_id, element_kind), {})
                if parsed in ordering:
                    errors.append(
                        f"{row_label}: duplicate sequence {parsed} within "
                        f"({kind!r}, {group_id!r}, {element_kind!r}); "
                        f"first seen at {label}:{ordering[parsed]}"
                    )
                else:
                    ordering[parsed] = i

    for kind, group_id, element_kind, station in sorted(station_wide & component_scoped):
        errors.append(
            f"{label}: group ({kind!r}, {group_id!r}) has both a station-wide and a "
            f"component-specific membership for {element_kind} station {station!r}; "
            "the station-wide row already covers every component"
        )


def validate(
    bundle_path: str | Path,
    schema_path: str | Path = DEFAULT_SCHEMA,
    full: bool = False,
    manifest_schema_path: str | Path = DEFAULT_MANIFEST_SCHEMA,
):
    bundle_path = Path(bundle_path)
    schema_path = Path(schema_path)
    manifest_schema_path = Path(manifest_schema_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    manifest_schema = None
    if Draft202012Validator is not None:
        manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    bundle = Bundle(bundle_path)
    names = set(bundle.names())
    errors = []
    warnings = []

    if full:
        validate_full_dependencies(errors)
        if errors:
            return errors, warnings

    bundle_schema = schema["bundle"]
    fixed_required = set(bundle_schema["required_fixed_files"])
    optional = set(bundle_schema.get("optional_files", []))
    formats = bundle_schema["table_formats"]

    for name in fixed_required:
        if name not in names:
            errors.append(f"missing required file: {name}")
    if errors:
        return errors, warnings

    tables = {}
    table_headers = {}
    table_files = set()
    optional_tables = bundle_schema.get("optional_tables", [])
    table_order = list(bundle_schema["required_tables"]) + list(optional_tables)
    resolution_errors = {table_name: [] for table_name in table_order}
    for table_name in table_order:
        present = {f"{table_name}.{fmt}" for fmt in formats if f"{table_name}.{fmt}" in names}
        table_files.update(present)
        if table_name in optional_tables and not present:
            continue
        try:
            filename, header, rows = resolve_table(
                bundle,
                names,
                table_name,
                schema["tables"][table_name],
                formats,
                materialize_csv_rows=table_name != "data",
            )
        except ValidationError as exc:
            resolution_errors[table_name].append(str(exc))
            continue
        tables[table_name] = {"filename": filename, "header": header, "rows": rows}
        table_headers[table_name] = header

    allowed = fixed_required | optional | table_files
    for name in sorted(names - allowed):
        warnings.append(f"unknown file ignored: {name}")
    resolution_warnings = list(warnings)

    data_table = tables.get("data")
    csv_data_table = (
        data_table
        if data_table is not None and isinstance(data_table["rows"], _CsvDataRows)
        else None
    )
    if any(resolution_errors.values()):
        if csv_data_table is not None:
            try:
                _scan_csv_data(
                    csv_data_table,
                    check_unique=False,
                    validate_rows=False,
                )
            except ValidationError as exc:
                resolution_errors["data"].append(str(exc))
        for table_name in table_order:
            errors.extend(resolution_errors[table_name])
        return errors, warnings

    manifest_errors = []
    manifest_warnings = []
    try:
        manifest = parse_manifest(bundle.read_text("manifest.yaml"))
        if manifest_schema is not None:
            validate_manifest_schema(manifest, manifest_schema, manifest_errors)
        else:
            manifest_warnings.append(
                "jsonschema not installed; manifest schema validation skipped"
            )
        validate_manifest(manifest, schema, manifest_errors, manifest_warnings)
        validate_altitude_rule(manifest, table_headers, schema, manifest_errors)
    except ValidationError:
        # DictReader used to discover data-row width errors before parsing the
        # manifest. Preserve that precedence even though data.csv is now lazy.
        if csv_data_table is not None:
            try:
                _scan_csv_data(
                    csv_data_table,
                    check_unique=False,
                    validate_rows=False,
                )
            except ValidationError as exc:
                return [str(exc)], resolution_warnings
        raise

    table_errors = {table_name: [] for table_name in table_order}
    for table_name, table_schema in schema["tables"].items():
        table = tables.get(table_name)
        if table is None:  # Absent optional table.
            continue
        current_errors = table_errors[table_name]
        validate_table_columns(
            table["header"],
            table_schema,
            table["filename"],
            current_errors,
        )
        if table is csv_data_table:
            continue
        check_unique(
            table["rows"],
            table_schema.get("unique_key", []),
            table["filename"],
            current_errors,
        )

    pre_data_errors = bool(manifest_errors) or any(table_errors.values())
    data_scan = None
    if csv_data_table is not None:
        if pre_data_errors:
            tx_keys_for_scan = None
            rx_keys_for_scan = None
        else:
            tx_keys_for_scan = {
                (row["tx_station_id"], row["tx_component_id"])
                for row in tables["tx"]["rows"]
            }
            rx_keys_for_scan = {
                (row["rx_station_id"], row["rx_component_id"])
                for row in tables["rx"]["rows"]
            }
        try:
            data_scan = _scan_csv_data(
                csv_data_table,
                tx_keys_for_scan,
                rx_keys_for_scan,
                validate_rows=not pre_data_errors,
            )
        except ValidationError as exc:
            return [str(exc)], resolution_warnings
        table_errors["data"].extend(data_scan.unique_errors)

    errors.extend(manifest_errors)
    warnings.extend(manifest_warnings)
    for table_name in table_order:
        errors.extend(table_errors[table_name])

    if errors:
        return errors, warnings

    tx_rows = tables["tx"]["rows"]
    rx_rows = tables["rx"]["rows"]
    tx_keys = {(r["tx_station_id"], r["tx_component_id"]) for r in tx_rows}
    rx_keys = {(r["rx_station_id"], r["rx_component_id"]) for r in rx_rows}
    tx_by_key = {(r["tx_station_id"], r["tx_component_id"]): r for r in tx_rows}
    rx_by_key = {(r["rx_station_id"], r["rx_component_id"]): r for r in rx_rows}

    for i, row in enumerate(tx_rows, start=2):
        row_label = f"{tables['tx']['filename']}:{i}"
        validate_ids(row, row_label, ("tx_station_id", "tx_component_id"), errors)
        if row.get("geometry_type") not in schema["enums"]["geometry_type"]:
            errors.append(f"{row_label}: geometry_type is invalid")
        validate_notes(row, row_label, errors)
        validate_point_columns(row_label, row, is_tx=True, errors=errors)
        validate_nav_columns(row, row_label, errors, warnings)

    for i, row in enumerate(rx_rows, start=2):
        row_label = f"{tables['rx']['filename']}:{i}"
        validate_ids(row, row_label, ("rx_station_id", "rx_component_id"), errors)
        geometry_type = row.get("geometry_type")
        if geometry_type not in schema["enums"]["geometry_type"]:
            errors.append(f"{row_label}: geometry_type is invalid")
        validate_point_columns(row_label, row, is_tx=False, errors=errors)
        component = row.get("rx_component_id", "")
        if isinstance(component, str) and component in CANONICAL_RX_COMPONENT_GEOMETRY:
            required_geometry = CANONICAL_RX_COMPONENT_GEOMETRY[component]
            if geometry_type != required_geometry:
                errors.append(
                    f"{row_label}: canonical component {component} must use geometry_type={required_geometry}"
                )
        validate_notes(row, row_label, errors)
        validate_nav_columns(row, row_label, errors, warnings)

    tx_vertices = group_vertices(
        tables["tx_vertices"]["rows"],
        ("tx_station_id", "tx_component_id"),
        tx_keys,
        tables["tx_vertices"]["filename"],
        errors,
    )
    rx_vertices = group_vertices(
        tables["rx_vertices"]["rows"],
        ("rx_station_id", "rx_component_id"),
        rx_keys,
        tables["rx_vertices"]["filename"],
        errors,
    )
    validate_vertex_counts(
        tx_vertices, tx_by_key, tables["tx_vertices"]["filename"], errors, warnings
    )
    validate_vertex_counts(
        rx_vertices, rx_by_key, tables["rx_vertices"]["filename"], errors, warnings
    )

    if data_scan is not None:
        errors.extend(data_scan.row_errors)
        has_dc = data_scan.has_dc
    else:
        has_dc = False
        for i, row in enumerate(tables["data"]["rows"], start=2):
            if validate_data_row(
                row,
                f"{tables['data']['filename']}:{i}",
                tx_keys,
                rx_keys,
                errors,
            ):
                has_dc = True

    if has_dc:
        field = manifest.get("field")
        content = field.get("content") if isinstance(field, dict) else None
        if content == "secondary":
            errors.append(
                "manifest field.content must not be secondary when data contains "
                "frequency = 0 rows; the secondary-field convention is not defined "
                "at DC (§3.12)"
            )

    if "groups" in tables:
        validate_groups(tables["groups"], schema, tx_keys, rx_keys, errors, warnings)

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate a csemx bundle")
    parser.add_argument("bundle", type=Path, help="bundle directory or .csemx.zip archive")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--manifest-schema", type=Path, default=DEFAULT_MANIFEST_SCHEMA)
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "require PyYAML, jsonschema, pyproj, and pyarrow for production "
            "conformance validation"
        ),
    )
    args = parser.parse_args()

    try:
        errors, warnings = validate(
            args.bundle,
            args.schema,
            full=args.full,
            manifest_schema_path=args.manifest_schema,
        )
    except ValidationError as exc:
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


if __name__ == "__main__":
    raise SystemExit(main())
