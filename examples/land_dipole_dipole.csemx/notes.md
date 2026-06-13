# Land CSEM — inline dipole–dipole (example)

Synthetic example bundle. A single grounded electric bipole transmitter (`TX1/E1`,
400 m) and three inline grounded electric-dipole receivers (`R1`–`R3`, 200 m) at
increasing offset along one line.

Demonstrates:
- inline electric `wire` Tx and Rx geometry,
- transmitter-drive provenance via `tx_fundamental` (fundamentals 0.25 and
  0.5 Hz in this synthetic example),
- the `use` flag: the noisy high-frequency data at the far offset (`R3` at 1.25
  and 2.5 Hz) are delivered with honest errors but marked `use = 0`,
- one attempted but missing datum (`R3` at 3.75 Hz) encoded as
  `NaN,NaN,NaN,NaN` for `real`, `imag`, `err_real`, and `err_imag`, and marked
  `use = 0`,
- an `ext_line_id` extension column in `data.csv`, demonstrating the `ext_*`
  producer-extension escape hatch,
- `ext_grid_x`/`ext_grid_y` columns in `tx_vertices.csv` and
  `rx_vertices.csv`, carrying the client's local survey-grid coordinates of each
  vertex alongside the authoritative projected UTM `easting`/`northing`
  (§3.1, §6, §8).

## Local survey grid (provenance only)

The `ext_grid_x`/`ext_grid_y` columns give each vertex in the client's local
survey grid. A survey grid is normally a *rotated* frame aligned to the survey or
line directions, not to easting/northing; this synthetic example keeps it simple
as a pure offset (no rotation), with the grid origin at UTM 12N easting 551000,
northing 3624000:

    ext_grid_x = easting  − 551000
    ext_grid_y = northing − 3624000

The frame is carried purely as provenance so the client can cross-reference their
historical grid. The projected EPSG geometry
(`coordinate_system.epsg_horizontal: 32612`) remains authoritative, and a
conforming reader ignores the `ext_*` columns entirely. A real (rotated) grid is
described the same way: csemx has no structured local-grid frame (a registered
projected EPSG CRS is always the delivered geometry), so any origin/rotation
lives here in `notes.md`, never as a manifest field.

All values are synthetic and not from any real survey.
