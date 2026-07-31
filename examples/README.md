# csemx example bundles

Synthetic, validating example bundles covering a compact set of representative
controlled-source EM acquisition styles. Values are order-of-magnitude synthetic
responses, not real survey data or benchmark forward responses. Validate the
CSV-only examples with:

```
python3 tools/validate_csemx.py examples/<name>.csemx
```

The mixed Parquet example requires `pyarrow` in the Python environment running
the validator.

The public example set is:

| public bundle | configuration | exercises |
| ------ | ------------- | --------- |
| `example.csemx` | mixed land/borehole sampler (matches spec §13) | every geometry flavor: wire/loop/point Tx, E-wire/B-point/B-loop Rx; UTC acquisition timestamps |
| `example_mixed_parquet.csemx` | same geometry as `example.csemx`, with `data.parquet` | mixed CSV/Parquet delivery; string-typed IDs in Parquet |
| `land_dipole_dipole.csemx` | land CSEM, inline dipole–dipole | grounded HED Tx + inline E-dipole Rx at increasing offset; `tx_fundamental`; `use=0`; `NaN` missing datum; `ext_line_id` extension |
| `land_grid_lines.csemx` | land CSEM grid, two intersecting lines | the optional `groups.csv` table (§10): a station on two crossing lines (many-to-many membership); `sequence` as ranks with gaps; a fixed wire Tx shooting an Rx line without being a member of it; one line with independent TX and RX sequences; component-level `array` membership |
| `seafloor_vector.csemx` | seafloor node + deep-towed 300 m HED | moving Tx; `altitude.reference: seafloor`; vertical `Ez` dipole; negative `elev`; `use` flag |
| `airborne_hem.csemx` | airborne frequency-domain EM (HEM) | moving point-dipole bird; coplanar vs coaxial via `azimuth_deg`/`dip_deg`; `altitude.reference: ground`; `field.content: secondary` (secondary `T/A`, primary from geometry; ppm is derived); `nav_*` attitude/uncertainty columns and sub-second `time_utc` (§3.13) |

Each `.csemx` directory is an unpacked bundle (`manifest.yaml` + the five
required tables, plus an optional `notes.md` and an optional `groups.csv`
element-membership table, spec §10); `example.csemx.zip` is the archived form
showing the preferred single-top-level-directory delivery shape.

Most example bundles are kept in CSV form for readability. The v1.0 specification
allows any required table to be delivered as Parquet (`<table>.parquet`) instead
of CSV; `example_mixed_parquet.csemx` exercises that path by using
`data.parquet`.

## Fill-in template: `template.csemx`

`template.csemx` is **not** a worked example — it is an editable, non-normative
starting point for producers assembling a bundle by hand (in a text editor or
spreadsheet, no programming required). It contains pre-headed CSV tables with
`REPLACE`-marked placeholder rows, a fully commented `manifest.yaml`, a
`notes.md` skeleton, an optional `groups.csv` starter, and a `README.md` with
step-by-step fill-in instructions.

Unlike the worked examples above, the template **intentionally fails
validation as shipped** (placeholder coordinates and measurements are blank),
so a half-filled copy cannot pass as a real delivery; it validates only once
filled in. `tools/check_examples.sh` therefore skips it.
