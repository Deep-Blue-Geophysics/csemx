#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import shutil
import sys
import tempfile
import unittest
import importlib
from pathlib import Path

# Make the source package importable from a checkout without installation.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))

validate_csemx = importlib.import_module("csemx.validation")
import csemx

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - exercised only without pyarrow.
    pa = None
    pq = None


SCHEMA = ROOT / "schemas" / "csemx-validator-metadata.json"
EXAMPLE = ROOT / "examples" / "example.csemx"
EXAMPLE_MIXED_PARQUET = ROOT / "examples" / "example_mixed_parquet.csemx"
AIRBORNE_HEM = ROOT / "examples" / "airborne_hem.csemx"
EXAMPLE_ACQUIRED_INTERVAL = (
    'acquired_start: "2026-05-01T14:32:00Z"\n'
    '  acquired_end: "2026-05-01T18:47:00Z"'
)


def rewrite_csv(path: Path, mutator):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames
    if fieldnames is None:
        raise AssertionError(f"{path} has no CSV header")

    mutator(rows)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def replace_text(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(f"{path} does not contain expected text: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class ValidatorRegressionTests(unittest.TestCase):
    def copy_example(self):
        tempdir = tempfile.TemporaryDirectory()
        bundle = Path(tempdir.name) / "example.csemx"
        shutil.copytree(EXAMPLE, bundle)
        self.addCleanup(tempdir.cleanup)
        return bundle

    def validate_bundle(self, bundle):
        return validate_csemx.validate(bundle, SCHEMA)

    def validate_bundle_without_pyyaml(self, bundle):
        original_yaml = validate_csemx.yaml
        self.addCleanup(setattr, validate_csemx, "yaml", original_yaml)
        validate_csemx.yaml = None
        return self.validate_bundle(bundle)

    @unittest.skipIf(
        validate_csemx.Draft202012Validator is None, "jsonschema is not installed"
    )
    def test_manifest_schema_rejects_units_block(self):
        # Units are fixed by the spec (§3.6) and not carried in the bundle, so a
        # leftover `units:` block is now an unknown top-level key, not valid.
        bundle = self.copy_example()
        manifest = bundle / "manifest.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8") + '\nunits:\n  rx_point_b: "T/A"\n'
        )

        errors, _warnings = self.validate_bundle(bundle)

        self.assertTrue(
            any(
                "Additional properties are not allowed" in error and "units" in error
                for error in errors
            ),
            errors,
        )

    def test_manifest_schema_skip_is_warning_in_default_mode(self):
        bundle = self.copy_example()
        original_draft_validator = validate_csemx.Draft202012Validator
        self.addCleanup(
            setattr,
            validate_csemx,
            "Draft202012Validator",
            original_draft_validator,
        )

        validate_csemx.Draft202012Validator = None
        errors, warnings = self.validate_bundle(bundle)

        self.assertEqual([], errors)
        self.assertIn(
            "jsonschema not installed; manifest schema validation skipped",
            warnings,
        )

    @unittest.skipIf(
        validate_csemx.Draft202012Validator is None, "jsonschema is not installed"
    )
    def test_manifest_schema_rejects_unknown_top_level_key(self):
        bundle = self.copy_example()
        manifest = bundle / "manifest.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\nextra: true\n")

        errors, _warnings = self.validate_bundle(bundle)

        self.assertTrue(
            any(
                "Additional properties are not allowed" in error and "extra" in error
                for error in errors
            ),
            errors,
        )

    @unittest.skipIf(
        validate_csemx.Draft202012Validator is None, "jsonschema is not installed"
    )
    def test_manifest_schema_rejects_string_epsg(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            "  epsg_horizontal: 32612",
            '  epsg_horizontal: "32612"',
        )

        errors, _warnings = self.validate_bundle(bundle)

        self.assertTrue(
            any("manifest.coordinate_system.epsg_horizontal" in error for error in errors),
            errors,
        )

    @unittest.skipIf(validate_csemx.CRS is None, "pyproj is not installed")
    def test_horizontal_epsg_rejects_non_meter_projected_crs(self):
        # EPSG:2225 (NAD83 / California zone 1, ftUS) is_projected but uses US
        # survey feet, not meters (§3.1). It must be rejected even though it would
        # pass a bare is_projected check.
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            "  epsg_horizontal: 32612",
            "  epsg_horizontal: 2225",
        )

        errors, _warnings = self.validate_bundle(bundle)

        self.assertTrue(
            any("must use meter axis units" in error for error in errors),
            errors,
        )

    @unittest.skipIf(validate_csemx.CRS is None, "pyproj is not installed")
    def test_vertical_epsg_rejects_non_meter_height_axis(self):
        # EPSG:6360 is a vertical CRS in US survey feet. csemx stores `elev` in
        # meters (§3.2), so vertical CRSs must expose a meter height axis.
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            "  epsg_vertical: 4979",
            "  epsg_vertical: 6360",
        )

        errors, _warnings = self.validate_bundle(bundle)

        self.assertTrue(
            any("must use a meter height axis" in error for error in errors),
            errors,
        )

    def test_manifest_version_rejects_padded_minor(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            '  version: "1.0"',
            '  version: "1.00"',
        )

        errors, _warnings = self.validate_bundle(bundle)

        self.assertIn("manifest format.version must be canonical MAJOR.MINOR", errors)

    def test_manifest_identity_strings_must_not_be_whitespace_only(self):
        cases = [
            ('  name: "Example"', '  name: "   "', "manifest survey.name is required"),
            (
                '  contractor: "Synthetic Producer"',
                '  contractor: "   "',
                "manifest survey.contractor is required",
            ),
            (
                '  contractor_reference: "Example 0001"',
                '  contractor_reference: "   "',
                "manifest survey.contractor_reference is required",
            ),
        ]
        for old, new, expected in cases:
            with self.subTest(field=expected):
                bundle = self.copy_example()
                replace_text(bundle / "manifest.yaml", old, new)

                errors, _warnings = self.validate_bundle(bundle)

                self.assertIn(expected, errors)

    @unittest.skipIf(pa is None or pq is None, "pyarrow is not installed")
    def test_parquet_schema_rejects_string_numeric_column(self):
        tempdir = tempfile.TemporaryDirectory()
        bundle = Path(tempdir.name) / "example_mixed_parquet.csemx"
        shutil.copytree(EXAMPLE_MIXED_PARQUET, bundle)
        self.addCleanup(tempdir.cleanup)

        table = pq.read_table(bundle / "data.parquet")
        arrays = []
        for column in table.column_names:
            if column == "frequency":
                values = [str(value.as_py()) for value in table[column]]
                arrays.append(pa.array(values, type=pa.string()))
            else:
                arrays.append(table[column])
        bad_table = pa.Table.from_arrays(arrays, names=table.column_names)
        pq.write_table(bad_table, bundle / "data.parquet")

        errors, _warnings = self.validate_bundle(bundle)

        self.assertTrue(
            any(
                "data.parquet: column 'frequency' must be a Parquet double (float64)" in error
                for error in errors
            ),
            errors,
        )

    @unittest.skipIf(pa is None or pq is None, "pyarrow is not installed")
    def test_parquet_schema_rejects_float32_numeric_column(self):
        tempdir = tempfile.TemporaryDirectory()
        bundle = Path(tempdir.name) / "example_mixed_parquet.csemx"
        shutil.copytree(EXAMPLE_MIXED_PARQUET, bundle)
        self.addCleanup(tempdir.cleanup)

        table = pq.read_table(bundle / "data.parquet")
        arrays = []
        for column in table.column_names:
            if column == "frequency":
                values = [value.as_py() for value in table[column]]
                arrays.append(pa.array(values, type=pa.float32()))
            else:
                arrays.append(table[column])
        bad_table = pa.Table.from_arrays(arrays, names=table.column_names)
        pq.write_table(bad_table, bundle / "data.parquet")

        errors, _warnings = self.validate_bundle(bundle)

        self.assertTrue(
            any(
                "data.parquet: column 'frequency' must be a Parquet double (float64)" in error
                for error in errors
            ),
            errors,
        )

    def test_full_validation_requires_standard_dependencies(self):
        bundle = self.copy_example()
        original_yaml = validate_csemx.yaml
        original_draft_validator = validate_csemx.Draft202012Validator
        original_crs = validate_csemx.CRS
        original_pa = validate_csemx.pa
        original_pq = validate_csemx.pq
        self.addCleanup(setattr, validate_csemx, "yaml", original_yaml)
        self.addCleanup(
            setattr,
            validate_csemx,
            "Draft202012Validator",
            original_draft_validator,
        )
        self.addCleanup(setattr, validate_csemx, "CRS", original_crs)
        self.addCleanup(setattr, validate_csemx, "pa", original_pa)
        self.addCleanup(setattr, validate_csemx, "pq", original_pq)

        validate_csemx.yaml = None
        validate_csemx.Draft202012Validator = None
        validate_csemx.CRS = None
        validate_csemx.pa = None
        validate_csemx.pq = None

        errors, warnings = validate_csemx.validate(bundle, SCHEMA, full=True)

        self.assertEqual([], warnings)
        self.assertTrue(any("requires PyYAML" in error for error in errors), errors)
        self.assertTrue(any("requires jsonschema" in error for error in errors), errors)
        self.assertTrue(any("requires pyproj" in error for error in errors), errors)
        self.assertTrue(any("requires pyarrow" in error for error in errors), errors)

    def test_custom_rx_component_id_does_not_infer_geometry_from_prefix(self):
        bundle = self.copy_example()

        def rename_rx(rows):
            for row in rows:
                if row["rx_component_id"] == "Ex":
                    row["rx_component_id"] = "Bipole"

        rewrite_csv(bundle / "rx.csv", rename_rx)
        rewrite_csv(bundle / "rx_vertices.csv", rename_rx)
        rewrite_csv(bundle / "data.csv", rename_rx)

        errors, _warnings = self.validate_bundle(bundle)
        self.assertEqual([], errors)

    def test_conventional_electric_rx_id_requires_wire_geometry(self):
        bundle = self.copy_example()

        def make_ex_loop(rows):
            for row in rows:
                if row["rx_component_id"] == "Ex":
                    row["geometry_type"] = "loop"

        rewrite_csv(bundle / "rx.csv", make_ex_loop)

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(
            any("canonical component Ex must use geometry_type=wire" in error for error in errors),
            errors,
        )

    def test_conventional_magnetic_point_rx_id_requires_point_geometry(self):
        bundle = self.copy_example()

        def make_bx_wire(rows):
            for row in rows:
                if row["rx_component_id"] == "Bx":
                    row["geometry_type"] = "wire"
                    row["azimuth_deg"] = ""
                    row["dip_deg"] = ""

        rewrite_csv(bundle / "rx.csv", make_bx_wire)

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(
            any("canonical component Bx must use geometry_type=point" in error for error in errors),
            errors,
        )

    def test_tx_geometry_type_must_be_known_enum(self):
        bundle = self.copy_example()

        def make_tx_geometry_invalid(rows):
            for row in rows:
                if row["tx_station_id"] == "TX01" and row["tx_component_id"] == "E1":
                    row["geometry_type"] = "electric"

        rewrite_csv(bundle / "tx.csv", make_tx_geometry_invalid)

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(any("tx.csv:2: geometry_type is invalid" in error for error in errors), errors)

    def test_rx_geometry_type_must_be_known_enum(self):
        bundle = self.copy_example()

        def make_rx_geometry_invalid(rows):
            for row in rows:
                if row["rx_component_id"] == "Ex":
                    row["geometry_type"] = "electric"

        rewrite_csv(bundle / "rx.csv", make_rx_geometry_invalid)

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(any("rx.csv:2: geometry_type is invalid" in error for error in errors), errors)

    def test_station_ids_have_64_character_limit(self):
        cases = [
            ("tx.csv", "TX01", "X" * 65, "tx.csv:2:tx_station_id: invalid value"),
            ("rx.csv", "001", "R" * 65, "rx.csv:2:rx_station_id: invalid value"),
        ]
        for filename, old, new, expected in cases:
            with self.subTest(filename=filename):
                bundle = self.copy_example()
                replace_text(bundle / filename, old, new)

                errors, _warnings = self.validate_bundle(bundle)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_row_notes_have_1024_character_limit(self):
        cases = [
            ("tx.csv", "tx_station_id,tx_component_id,geometry_type", "TX01,E1,wire"),
            ("rx.csv", "rx_station_id,rx_component_id,geometry_type", "001,Ex,wire"),
        ]
        for filename, header_prefix, row_prefix in cases:
            with self.subTest(filename=filename):
                bundle = self.copy_example()
                replace_text(bundle / filename, header_prefix, f"{header_prefix},notes")
                replace_text(bundle / filename, row_prefix, f"{row_prefix},{'x' * 1025}")

                errors, _warnings = self.validate_bundle(bundle)
                self.assertTrue(
                    any(":notes: must be at most 1024 characters" in error for error in errors),
                    errors,
                )

    def test_loop_self_intersection_is_warning_not_error(self):
        bundle = self.copy_example()
        bowtie = {
            "0": ("0.0", "0.0", "0.0"),
            "1": ("1.0", "1.0", "0.0"),
            "2": ("0.0", "1.0", "0.0"),
            "3": ("1.0", "0.0", "0.0"),
        }

        def make_tx_loop_bowtie(rows):
            for row in rows:
                if row["tx_station_id"] == "TX02" and row["tx_component_id"] == "M1":
                    easting, northing, elev = bowtie[row["vertex_index"]]
                    row["easting"] = easting
                    row["northing"] = northing
                    row["elev"] = elev

        rewrite_csv(bundle / "tx_vertices.csv", make_tx_loop_bowtie)

        errors, warnings = self.validate_bundle(bundle)
        self.assertEqual([], errors)
        self.assertTrue(any("self-intersects" in warning for warning in warnings), warnings)

    def test_format_version_accepts_older_minor_for_supported_major(self):
        errors = []
        validate_csemx.validate_format_version("1.0", "1.2", errors)
        self.assertEqual([], errors)

    def test_format_version_rejects_newer_minor_and_other_major(self):
        errors = []
        validate_csemx.validate_format_version("1.3", "1.2", errors)
        validate_csemx.validate_format_version("2.0", "1.2", errors)
        self.assertEqual(2, len(errors))

    def test_format_version_rejects_noncanonical_forms(self):
        errors = []
        validate_csemx.validate_format_version("1.00", "1.2", errors)
        validate_csemx.validate_format_version("01.0", "1.2", errors)
        validate_csemx.validate_format_version("1.000", "1.2", errors)
        self.assertEqual(3, len(errors))

    def test_unknown_columns_must_use_extension_prefix(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "tx.csv",
            "tx_station_id,tx_component_id,geometry_type,azimuth_deg,dip_deg,point_moment_area_m2",
            "tx_station_id,tx_component_id,geometry_type,azimuth_deg,dip_deg,point_moment_area_m2,bad_col",
        )

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(any("unexpected column 'bad_col'" in error for error in errors), errors)

    def test_legacy_type_columns_are_rejected(self):
        cases = [
            (
                "tx.csv",
                "tx_station_id,tx_component_id,geometry_type",
                "tx_station_id,tx_component_id,source_type,geometry_type",
                "TX01,E1,wire",
                "TX01,E1,electric,wire",
                "unexpected column 'source_type'",
            ),
            (
                "rx.csv",
                "rx_station_id,rx_component_id,geometry_type",
                "rx_station_id,rx_component_id,sensor_type,geometry_type",
                "001,Ex,wire",
                "001,Ex,electric,wire",
                "unexpected column 'sensor_type'",
            ),
        ]
        for filename, old_header, new_header, old_row, new_row, expected in cases:
            with self.subTest(filename=filename):
                bundle = self.copy_example()
                replace_text(bundle / filename, old_header, new_header)
                replace_text(bundle / filename, old_row, new_row)

                errors, _warnings = self.validate_bundle(bundle)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_duplicate_frequency_keys_are_canonicalized(self):
        bundle = self.copy_example()
        data = bundle / "data.csv"
        lines = data.read_text(encoding="utf-8").splitlines()
        duplicate = lines[1].replace(",0.125,", ",1.25e-1,", 1)
        data.write_text("\n".join(lines + [duplicate]) + "\n", encoding="utf-8")

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(any("duplicate key" in error for error in errors), errors)

    def test_tx_fundamental_does_not_require_harmonic_relationship(self):
        bundle = self.copy_example()
        data = bundle / "data.csv"
        lines = data.read_text(encoding="utf-8").splitlines()
        lines[0] += ",tx_fundamental"
        first_fields = lines[1].split(",")
        first_fields[4] = "0.5"
        lines[1] = ",".join(first_fields) + ",0.25"
        for i in range(2, len(lines)):
            lines[i] += ","
        data.write_text("\n".join(lines) + "\n", encoding="utf-8")

        errors, _warnings = self.validate_bundle(bundle)

        self.assertEqual([], errors)

    def test_use_column_must_be_filled_when_present(self):
        bundle = self.copy_example()
        data = bundle / "data.csv"
        lines = data.read_text(encoding="utf-8").splitlines()
        lines[0] += ",use"
        lines[1] += ","
        for i in range(2, len(lines)):
            lines[i] += ",1"
        data.write_text("\n".join(lines) + "\n", encoding="utf-8")

        errors, _warnings = self.validate_bundle(bundle)

        self.assertIn("data.csv:2:use: missing integer value", errors)

    def test_malformed_manifest_mapping_reports_errors(self):
        bundle = self.copy_example()
        replace_text(bundle / "manifest.yaml", 'format:\n  name: csemx\n  version: "1.0"', "format: csemx")

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(any("manifest format must be a mapping" in error for error in errors), errors)

    def test_manifest_acquired_end_must_not_precede_start(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            EXAMPLE_ACQUIRED_INTERVAL,
            'acquired_start: "2026-05-02"\n  acquired_end: "2026-05-01"',
        )

        errors, _warnings = self.validate_bundle(bundle)
        self.assertIn("manifest survey.acquired_end must be on or after acquired_start", errors)

    def test_manifest_acquired_dates_are_allowed(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            EXAMPLE_ACQUIRED_INTERVAL,
            'acquired_start: "2026-05-01"\n  acquired_end: "2026-05-01"',
        )

        errors, _warnings = self.validate_bundle(bundle)
        self.assertEqual([], errors)

    def test_manifest_acquired_precision_must_match(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            EXAMPLE_ACQUIRED_INTERVAL,
            'acquired_start: "2026-05-01T14:32:00Z"\n  acquired_end: "2026-05-01"',
        )

        errors, _warnings = self.validate_bundle(bundle)
        self.assertIn(
            "manifest survey.acquired_start and acquired_end must both be dates or both be UTC timestamps",
            errors,
        )

    def test_manifest_acquired_values_must_use_exact_allowed_forms(self):
        invalid_values = [
            "2026/05/01",
            "May 1 2026",
            "2026-05-01T14:32:00",
            "2026-05-01T14:32:00+00:00",
            "2026-05-01T14:32Z",
            "2026-05-01T14:32:00.123Z",
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                bundle = self.copy_example()
                replace_text(
                    bundle / "manifest.yaml",
                    EXAMPLE_ACQUIRED_INTERVAL,
                    f'acquired_start: "{value}"\n  acquired_end: "2026-05-01T18:47:00Z"',
                )

                errors, _warnings = self.validate_bundle(bundle)
                self.assertTrue(
                    any(
                        "manifest survey.acquired_start: must be exactly YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ"
                        in error
                        for error in errors
                    ),
                    errors,
                )

    def test_manifest_unquoted_dates_are_rejected(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            EXAMPLE_ACQUIRED_INTERVAL,
            "acquired_start: 2026-05-01\n  acquired_end: 2026-05-01",
        )

        errors, _warnings = self.validate_bundle(bundle)
        self.assertTrue(
            any("must be a quoted string" in error for error in errors),
            errors,
        )

    def test_manifest_unquoted_dates_are_rejected_without_pyyaml(self):
        # The dependency-light fallback parser (no PyYAML) must reject unquoted
        # acquisition endpoints too, matching the PyYAML path.
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            EXAMPLE_ACQUIRED_INTERVAL,
            "acquired_start: 2026-05-01\n  acquired_end: 2026-05-01",
        )

        errors, _warnings = self.validate_bundle_without_pyyaml(bundle)
        self.assertTrue(
            any("must be a quoted string" in error for error in errors),
            errors,
        )

    def test_manifest_unquoted_timestamps_are_rejected_without_pyyaml(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            EXAMPLE_ACQUIRED_INTERVAL,
            "acquired_start: 2026-05-01T14:32:00Z\n  acquired_end: 2026-05-01T18:47:00Z",
        )

        errors, _warnings = self.validate_bundle_without_pyyaml(bundle)
        self.assertTrue(
            any("must be a quoted string" in error for error in errors),
            errors,
        )

    def test_manifest_quoted_dates_are_allowed_without_pyyaml(self):
        bundle = self.copy_example()
        replace_text(
            bundle / "manifest.yaml",
            EXAMPLE_ACQUIRED_INTERVAL,
            'acquired_start: "2026-05-01"\n  acquired_end: "2026-05-01"',
        )

        errors, _warnings = self.validate_bundle_without_pyyaml(bundle)
        self.assertEqual([], errors)

    def test_packaged_schemas_match_top_level_schemas(self):
        package_schema_dir = ROOT / "python" / "src" / "csemx" / "schemas"
        for filename in (
            "csemx-validator-metadata.json",
            "manifest.schema.json",
        ):
            with self.subTest(filename=filename):
                self.assertEqual(
                    (ROOT / "schemas" / filename).read_text(encoding="utf-8"),
                    (package_schema_dir / filename).read_text(encoding="utf-8"),
                )

    def test_public_api_read_write_validate_round_trip(self):
        bundle = csemx.read(EXAMPLE)
        target = Path(tempfile.mkdtemp()) / "roundtrip.csemx.zip"
        csemx.write(bundle, target)

        errors, _warnings = csemx.validate(target)

        self.assertEqual([], errors)

    def test_public_validate_accepts_string_path(self):
        errors, _warnings = csemx.validate(str(EXAMPLE))

        self.assertEqual([], errors)

    def test_writer_uses_canonical_nan_token(self):
        bundle = csemx.read(EXAMPLE)
        row = bundle.tables["data"].rows[0]
        for column in ("real", "imag", "err_real", "err_imag"):
            row[column] = math.nan

        target = Path(tempfile.mkdtemp()) / "nancheck.csemx"
        csemx.write(bundle, target)

        first_data_row = (target / "data.csv").read_text(encoding="utf-8").splitlines()[1]
        self.assertIn(",NaN,NaN,NaN,NaN", first_data_row)

    def test_writer_rejects_non_safe_zip_root(self):
        bundle = csemx.read(EXAMPLE)
        target = Path(tempfile.mkdtemp()) / "bad root.csemx.zip"

        with self.assertRaises(ValueError):
            csemx.write(bundle, target)

    def test_field_content_secondary_is_accepted(self):
        errors, _warnings = self.validate_bundle(AIRBORNE_HEM)
        self.assertEqual([], errors)

    def test_field_content_secondary_allows_wire_rows_under_free_space_convention(self):
        bundle = self.copy_example()
        manifest = bundle / "manifest.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8") + "\nfield:\n  content: secondary\n",
            encoding="utf-8",
        )

        errors, _warnings = self.validate_bundle(bundle)
        self.assertEqual([], errors)

    def test_field_content_invalid_value_is_rejected(self):
        bundle = self.copy_example()
        manifest = bundle / "manifest.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8") + "\nfield:\n  content: scattered\n",
            encoding="utf-8",
        )

        errors, _warnings = self.validate_bundle(bundle)
        self.assertIn("manifest field.content must be total or secondary", errors)


if __name__ == "__main__":
    unittest.main()
