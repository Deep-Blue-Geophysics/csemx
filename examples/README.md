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
| `example.csemx` | mixed land/borehole sampler (matches spec §12) | every geometry flavor: wire/loop/point Tx, E-wire/B-point/B-loop Rx; UTC acquisition timestamps |
| `example_mixed_parquet.csemx` | same geometry as `example.csemx`, with `data.parquet` | mixed CSV/Parquet delivery; string-typed IDs in Parquet |
| `land_dipole_dipole.csemx` | land CSEM, inline dipole–dipole | grounded HED Tx + inline E-dipole Rx at increasing offset; `tx_fundamental`; `use=0`; `NaN` missing datum; `ext_line_id` extension |
| `seafloor_vector.csemx` | seafloor node + deep-towed 300 m HED | moving Tx; `altitude.reference: seafloor`; vertical `Ez` dipole; negative `elev`; `use` flag |
| `airborne_hem.csemx` | airborne frequency-domain EM (HEM) | moving point-dipole bird; coplanar vs coaxial via `azimuth_deg`/`dip_deg`; `altitude.reference: ground`; `field.content: secondary` (secondary `T/A`, primary from geometry; ppm is derived) |

Each `.csemx` directory is an unpacked bundle (`manifest.yaml` + the five tables,
plus an optional `notes.md`); `example.csemx.zip` is the archived form showing the preferred
single-top-level-directory delivery shape.

Most example bundles are kept in CSV form for readability. The v1.0 specification
allows any required table to be delivered as Parquet (`<table>.parquet`) instead
of CSV; `example_mixed_parquet.csemx` exercises that path by using
`data.parquet`.
