# csemx Quickstart

A plain-language guide to assembling your first csemx bundle.

> This guide is **non-normative**: it explains, but it does not rule. The full
> rules live in the [specification](../csemx-specification.md). If anything here
> seems to disagree with the specification, the specification wins.

## Who this is for

You are a contractor or data provider who has been asked to deliver
frequency-domain CSEM data as a csemx bundle. You do not need to be a
programmer, and you do not need to install anything to follow this guide. By
the end you should know what goes in each file and be able to start filling
them in with your own survey.

## What a bundle is

A csemx bundle is a single file named like `mysurvey.csemx.zip`. It is an
**ordinary ZIP archive** — the same kind of ZIP file every operating system can
open. Inside the ZIP is one folder (its name is your choice, using only
letters, digits, `_`, `.`, and `-`), and inside that folder sit **six core
files**:

- `manifest.yaml` — a short text file stating the survey-wide facts every
  reader needs: survey name, contractor, acquisition dates, coordinate system,
  and sign convention.
- `tx.csv` — one row for each transmitter element, saying what kind of source
  it is.
- `tx_vertices.csv` — the surveyed positions (easting, northing, elevation)
  that trace each transmitter on the ground.
- `rx.csv` — one row for each receiver element, saying what kind of sensor it
  is.
- `rx_vertices.csv` — the surveyed positions that place each receiver.
- `data.csv` — the measurements: one row per measured value, tied to one
  transmitter, one receiver, and one frequency.

A bundle may additionally contain:

- `groups.csv` — optional labels that collect stations into named lines,
  arrays, or other groupings.
- `notes.md` — an optional free-text file where you describe the survey in
  your own words: instruments, processing history, anything a colleague should
  know.
- **Parquet equivalents** — any table may be delivered as a `.parquet` file
  instead of `.csv` (for example `data.parquet`). Parquet is a compressed
  binary format used for very large tables. If you are assembling a bundle by
  hand, use CSV.

Laid out as a file tree:

```text
mysurvey/
├── manifest.yaml
├── tx.csv
├── tx_vertices.csv
├── rx.csv
├── rx_vertices.csv
├── data.csv
├── groups.csv        (optional)
└── notes.md          (optional)
```

That is the whole format. The rest of this guide walks through a small example
of every file.

## Before you start: a warning about spreadsheets

> **Before entering data in Excel or similar software, format all station-ID
> and component-ID columns as text. Otherwise values such as `001` may be
> changed to `1`, and long identifiers may be reformatted or converted to
> scientific notation. Export tables as UTF-8 comma-delimited CSV files.**

After exporting, reopen the exported CSV file in a plain-text editor (Notepad,
TextEdit in plain-text mode, or similar) — not in the spreadsheet program —
and check:

- Leading zeros are still there: a station ID `001` has not become `1`.
- No identifier has been converted to a date or to scientific notation.
- Decimal values use a period (`1465.50`), not a comma.
- The column names in the header row are unchanged.
- Optional values you left blank are still blank — nothing has filled in `0`,
  `NA`, or anything else.

Spreadsheets are a fine way to assemble the tables if you follow these steps.
A plain-text editor avoids the problem entirely.

## A small example survey

The rest of this guide uses one tiny synthetic survey:

- One transmitter station `TX01` with a single grounded-wire source, component
  `E1`: a 400 m cable with an electrode at each end.
- Receiver station `001` with two sensors: an electric dipole `Ex` (two
  electrodes 100 m apart) and a vertical magnetic coil `Bz`.
- Receiver station `002` with one electric dipole `Ex`.
- Measurements at two frequencies, 0.5 Hz and 2 Hz.

All values are synthetic. Every excerpt below is complete and consistent: you
can trace any station or component ID from one table to the next.

### manifest.yaml

```yaml
format:
  name: csemx
  version: "1.0"

domain: frequency

survey:
  name: "Quickstart Example"
  revision: 1
  acquired_start: "2026-06-10"
  acquired_end: "2026-06-12"
  contractor: "Example Geophysics Ltd"
  contractor_reference: "EG-2026-042"

coordinate_system:
  epsg_horizontal: 32612

elevation:
  epsg_vertical: 4979

sign:
  time_dependence: "exp(+iwt)"
```

In plain terms:

- `format` and `domain` — write these exactly as shown for a version 1.0
  bundle.
- `survey` — your survey name, your company name, and your job or contract
  reference. `revision` starts at 1 and goes up by one each time you re-ship a
  corrected delivery. The acquisition dates are written in quotes; use either
  two plain dates or two full UTC timestamps, not a mixture.
- `coordinate_system.epsg_horizontal` — the EPSG code of the projected map
  grid (in meters) used for every easting and northing in the bundle. Here
  `32612` means WGS84 / UTM zone 12N. Your surveyor or processor will know the
  right code.
- `elevation.epsg_vertical` — the EPSG code defining what "elevation" means.
  `4979` is GPS (ellipsoidal) height, the recommended choice; `3855` is height
  above sea level (EGM2008 geoid).
- `sign.time_dependence` — the phase sign convention used in processing,
  written exactly as `exp(+iwt)` or `exp(-iwt)`. Ask whoever processed the
  data; it is not a guess.

The full rules for the manifest are in specification §4.

### tx.csv

One row per transmitter element:

```csv
tx_station_id,tx_component_id,geometry_type
TX01,E1,wire
```

- `tx_station_id` and `tx_component_id` together name this element. A station
  can hold several elements (for example two crossed cables), each with its
  own component ID.
- `geometry_type` is `wire` (an electric-dipole cable), `loop` (a closed
  loop), or `point` (a small coil treated as an oriented point).

A wire's position and direction come entirely from its vertices (next file),
so no other columns are needed here. A `point` transmitter would additionally
need `azimuth_deg`, `dip_deg`, and `point_moment_area_m2` columns for its coil
axis and area — see specification §5.

### tx_vertices.csv

The surveyed points that trace each transmitter:

```csv
tx_station_id,tx_component_id,vertex_index,easting,northing,elev
TX01,E1,0,551000.00,3625000.00,1478.00
TX01,E1,1,551400.00,3625000.00,1481.00
```

- The first two columns repeat the element's IDs from `tx.csv`, spelled
  identically.
- `vertex_index` counts 0, 1, 2, ... along the element. A wire needs at least
  two vertices, a loop at least three, a point exactly one.
- `easting` and `northing` are map-grid coordinates in meters; `elev` is
  height in meters, positive up.
- Vertex order carries meaning: for a wire transmitter the first vertex is the
  negative electrode and the last is the positive electrode (specification
  §3.4). List the points in the order that matches your wiring.

### rx.csv

One row per receiver element:

```csv
rx_station_id,rx_component_id,geometry_type,azimuth_deg,dip_deg
001,Ex,wire,,
001,Bz,point,0,90
002,Ex,wire,,
```

- Station `001` has two elements; station `002` has one.
- The electric dipoles are `wire` rows. Their orientation comes from their
  vertices, so `azimuth_deg` and `dip_deg` are left blank — a blank cell means
  "not applicable", and that is fine.
- The magnetic coil `Bz` is a `point` row, so it needs its axis: azimuth 0°,
  dip 90° means the coil axis points straight down.
- Names like `Ex` and `Bz` are conventional labels, but the format never reads
  direction from a name — geometry always comes from the vertex positions or
  the azimuth/dip values (specification §3.9).

### rx_vertices.csv

```csv
rx_station_id,rx_component_id,vertex_index,easting,northing,elev
001,Ex,0,552000.00,3625000.00,1466.00
001,Ex,1,552100.00,3625000.00,1465.00
001,Bz,0,552050.00,3625000.00,1465.50
002,Ex,0,552400.00,3625000.00,1459.00
002,Ex,1,552500.00,3625000.00,1458.00
```

- Each electric dipole has two vertices; for a wire receiver the first vertex
  is the voltmeter's positive terminal (specification §3.4).
- The point coil `Bz` has exactly one vertex.

### data.csv

One row per measured value:

```csv
tx_station_id,tx_component_id,rx_station_id,rx_component_id,frequency,real,imag,err_real,err_imag
TX01,E1,001,Ex,0.5,4.6e-7,-6.2e-8,1.1e-8,1.0e-8
TX01,E1,001,Ex,2,3.1e-7,-1.4e-7,1.3e-8,1.2e-8
TX01,E1,001,Bz,0.5,8.2e-12,-1.5e-12,3.0e-13,2.8e-13
TX01,E1,002,Ex,0.5,9.4e-8,-1.8e-8,4.0e-9,3.8e-9
TX01,E1,002,Ex,2,NaN,NaN,NaN,NaN
```

- The first four columns say which transmitter and which receiver produced
  the measurement, using the same IDs as the tables above.
- `frequency` is in hertz and is greater than zero (exactly `0` is reserved
  for DC data — specification §3.12).
- `real` and `imag` are the two parts of one complex measurement, normalized
  by transmitter current; `err_real` and `err_imag` are their uncertainties
  (zero or positive). The measurement unit is fixed by the receiver type —
  volts per amp for wires and loops, tesla per amp for point coils
  (specification §3.6) — so no unit column is ever written.
- The last row shows a **missing** measurement: it was attempted but produced
  no usable result, so all four measurement values are `NaN` ("not a
  number"). They go missing together — never fill in some and not others, and
  never leave them blank.
- No two rows may repeat the same transmitter + receiver + frequency
  combination.

## How the tables connect

Every table is linked by the same simple idea: **matching ID columns**.

Take the transmitter. The row `TX01,E1,wire` in `tx.csv` declares that the
element exists. The two rows in `tx_vertices.csv` that also say `TX01,E1`
place it on the ground. And every row of `data.csv` that says `TX01,E1`
records a measurement made with it. The same pattern connects `rx.csv`,
`rx_vertices.csv`, and `data.csv` through the receiver IDs — trace `001` and
`Ex` through the excerpts above and you will cross three files.

For this to work, IDs must match **exactly, character for character**. `TX01`
and `tx01` are different. `001` and `1` are different — which is why the
spreadsheet warning above matters so much. IDs use only letters, digits, `_`,
and `-`, and they are text, not numbers.

In database language, a column whose values must match another table is
called a *foreign key* (see the glossary). You do not need the term to build a
bundle — you only need the IDs to line up.

## Optional: groups.csv

If your stations are organized into survey lines, arrays, or other named
collections, you can record that in `groups.csv`. Using the same stations as
above, one survey line containing the transmitter and both receivers:

```csv
group_kind,group_id,element_kind,station_id,component_id,sequence
line,L100,tx,TX01,,0
line,L100,rx,001,,0
line,L100,rx,002,,1
```

- `group_kind` names the kind of grouping (`line` is the one kind defined by
  the specification; `array` is recommended; other names are yours to choose).
- `element_kind` says whether the row refers to a transmitter (`tx`) or
  receiver (`rx`) station, and `station_id` must match `tx.csv` or `rx.csv`
  accordingly.
- A blank `component_id` means the whole station belongs to the group; fill
  it in to include only one component.
- `sequence` gives the order along a line, counted separately for
  transmitters and receivers. Leave it blank if the order is unknown.

Grouping is purely descriptive — it never changes what a measurement means
(specification §10). If you have no useful groupings, omit the file.

## Packing the ZIP

Put every file in one folder (for example `mysurvey/`), then compress that
folder into a ZIP archive using your operating system's built-in "compress"
feature, and name the result `mysurvey.csemx.zip`. The ZIP must contain the
folder itself at the top level — not the loose files.

## Checking your work

**You do not need validation software to inspect or begin creating a csemx
bundle. The files are ordinary YAML, CSV, Markdown, or Parquet files.
Producers should validate completed bundles before delivery.**

There are three levels of support:

**1. Manual inspection.** Open the files in a plain-text editor and check them
yourself. The most valuable checks:

- The header row of each table spells the column names exactly as the
  specification does: lower-case, with underscores (`tx_station_id`, not
  `TX Station ID`).
- Every transmitter named in `data.csv` (its station ID + component ID pair)
  has a row in `tx.csv` and positions in `tx_vertices.csv`; every receiver
  likewise in `rx.csv` and `rx_vertices.csv`. IDs match exactly, including
  leading zeros and letter case.
- No station + component pair appears twice in `tx.csv` or `rx.csv`, and no
  two `data.csv` rows share the same transmitter + receiver + frequency.
- Vertex counts are right: exactly 1 for a point, at least 2 for a wire, at
  least 3 for a loop, with `vertex_index` counting 0, 1, 2, ... for each
  element.
- In `data.csv`, the four measurement columns (`real`, `imag`, `err_real`,
  `err_imag`) are either all filled or all `NaN` in each row — never blank,
  and never partly filled.
- Blank cells appear only in optional or not-applicable fields; `NaN` appears
  only in the four measurement columns.

**2. First-bundle assistance.** If you are preparing your first csemx
delivery, you can send a draft bundle to the project feedback address,
<csemx@deepbluegeophysics.com>, and ask for it to be checked. The Feedback
section of the
[repository README](https://github.com/Deep-Blue-Geophysics/csemx#feedback)
lists the other feedback channels and how comments are handled.

**3. Standalone validator (planned).** After v1.0, the project plans a
standalone validator: a single downloadable program for Windows, macOS, and
Linux that checks a bundle and lists any problems, with nothing else to
install. Until then, the repository also ships a Python-based validator for
those who use Python (see the README), but it is not required to produce a
correct bundle.

## Glossary

- **bundle** — the whole delivery: one folder of csemx files packed into a
  `.csemx.zip` archive.
- **manifest** — the `manifest.yaml` file: the bundle's cover sheet, stating
  survey-wide facts such as the coordinate system and sign convention.
- **table** — data arranged in rows and columns, stored as a CSV or Parquet
  file. `tx.csv` and `data.csv` above are tables.
- **row and column** — a row is one record (one transmitter element, one
  measurement); a column is one named field every row can fill in (such as
  `easting`). The first line of a CSV file names the columns.
- **datum** — one measured value. In csemx, the complex response in one row
  of `data.csv`: its `real` and `imag` parts together.
- **component** — one individual source or sensor element at a station, named
  by a component ID such as `E1`, `Ex`, or `Bz`. Station `001` in the `rx.csv`
  example above has two components.
- **foreign key** — a column whose values must match values in another table.
  `tx_station_id` in `data.csv` is a foreign key: every value in it must also
  appear in `tx.csv` (see "How the tables connect" above).
- **unique key** — the column, or combination of columns, that no two rows of
  a table may share. In `rx.csv` the pair `rx_station_id` + `rx_component_id`
  is the unique key: each element is listed once.
- **normative** — binding. A normative rule in the specification must be
  followed for a bundle to be valid.
- **non-normative** — explanatory only. This quickstart is non-normative: it
  helps you read the rules but never replaces them.
- **required** — must be present and filled in (said of a file, column, or
  value).
- **optional** — may be left out entirely, or left blank where it does not
  apply — like `azimuth_deg` for the wire rows in the `rx.csv` example.
- **validator** — software that checks a finished bundle against the
  specification's rules and reports any problems.
- **extension column** — an extra, producer-defined column whose name starts
  with `ext_` (for example `ext_grid_x`). It carries your own additional
  information; standard readers are free to ignore it.

## Where to go next

- The [specification](../csemx-specification.md) — the full, normative rules,
  including a larger worked example (§13) with loop and borehole geometries.
- The [example bundles](../examples/README.md) — complete small bundles you
  can open, inspect, and copy from, including a fill-in **template bundle**
  (`examples/template.csemx/`) with pre-headed tables and a manifest whose
  every key is explained in comments.
- The [rationale](../csemx-rationale.md) — why the format is designed the way
  it is.
