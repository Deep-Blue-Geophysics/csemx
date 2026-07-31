# csemx fill-in template

This folder is a **template** for producing a csemx bundle by hand — no
programming required. Every file is pre-headed with the correct column names;
you replace the placeholder rows and values with your survey.

Every placeholder is marked `REPLACE`. The template **intentionally fails
validation** as shipped (placeholder rows have blank coordinates and
measurements), so a half-filled copy cannot be mistaken for a real delivery.
It only validates once you have filled everything in.

The authoritative definitions live in `csemx-specification.md` (section
numbers referenced below). This README is a plain-language guide, not a
replacement for the spec.

## Before you start: spreadsheet software

Before entering data in Excel or similar software, format all station-ID and
component-ID columns as text. Otherwise values such as 001 may be changed to
1, and long identifiers may be reformatted or converted to scientific
notation. Export tables as UTF-8 comma-delimited CSV files.

After exporting, reopen the exported CSV in a plain-text editor (not the
spreadsheet program) and verify:

- leading zeros are preserved (`001` is still `001`);
- identifiers have not been converted to dates or scientific notation;
- decimal values use a period (`.`), not a comma;
- column names in the header row are unchanged;
- blank optional values are still blank (not `0`, `NULL`, or `N/A`).

## Filling in the bundle, step by step

Work in this order — later files refer back to earlier ones.

### Step 1: `manifest.yaml`

Open it in a text editor and follow the comments: every key is explained in
place. Replace every value marked `REPLACE`. Keys marked optional stay
commented out unless you need them.

### Step 2: `tx.csv` and `rx.csv` (what your transmitters and receivers are)

One row per element: a `(station_id, component_id)` pair. A station groups
co-located elements; the component labels each one (e.g. receiver station
`0100` with components `Ex` and `Ey`). IDs may use only letters, digits,
underscore, and hyphen — no spaces — and they are the join keys that must match
exactly (including case) across all the other files.

- `geometry_type` is one of `wire` (grounded/electric dipole along a path),
  `loop` (closed loop), or `point` (small magnetic coil treated as a point).
- `azimuth_deg` / `dip_deg`: fill **only** for `point` rows (the coil axis:
  azimuth clockwise from true north in `[0, 360)`, dip positive down in
  `[-90, 90]`). Leave blank for `wire` and `loop` rows.
- `point_moment_area_m2` (tx.csv only): fill **only** for `point` transmitter
  rows — the effective single-turn coil area in m². Leave blank otherwise.
- Duplicate the placeholder row for as many elements as you have, then make
  sure no `REPLACE` text remains.

Optional columns not pre-headed here (`notes`, `nav_*` navigation/attitude
columns for moving platforms, `ext_*` extensions) may be added; see spec
§5, §7, and §3.13.

### Step 3: `tx_vertices.csv` and `rx_vertices.csv` (where they are)

One row per vertex of each element, keyed by the same station and component
IDs as Step 2:

- `vertex_index` starts at **0** and counts up without gaps within each
  element. A `point` element has exactly 1 vertex, a `wire` at least 2, a
  `loop` at least 3 (do **not** repeat the first vertex to close a loop —
  closure is implicit).
- `easting` / `northing`: meters in the projected system declared by
  `epsg_horizontal`. `elev`: meters, positive up, in the datum declared by
  `epsg_vertical`.
- Vertex order matters — it defines the element's polarity (spec §3.4). For a
  wire receiver, the first vertex is the voltmeter `+` terminal; for a wire
  transmitter, the last vertex is the `+` injection electrode.

### Step 4: `data.csv` (the measurements)

One row per measurement, keyed by the transmitter and receiver IDs of Step 2:

- `frequency`: hertz; `0` means a DC / static-limit datum (spec §3.12).
- `real` / `imag`: the complex response, calibrated and normalized per amp of
  transmitter current (spec §3.6–§3.7). Units are fixed by the receiver's
  `geometry_type`: `V/A` for wire and loop receivers, `T/A` for point
  receivers.
- `err_real` / `err_imag`: absolute one-sigma uncertainties, zero or greater.
- A missing (attempted but unusable) datum has `NaN` in **all four** of
  `real`, `imag`, `err_real`, `err_imag` — never blanks.
- Optional columns may be added: `use` (`0` = delivered but not recommended,
  `1` = good; omit the column if everything is good), `tx_fundamental` (the
  drive's fundamental in Hz, where meaningful), and `ext_*` extensions.

### Step 5 (optional): `groups.csv` and `notes.md`

`groups.csv` assigns transmitter/receiver elements to named groups such as
survey lines or arrays (spec §10). It is **optional — delete the file if you
do not need groupings**. CSV files cannot carry comments, so its guidance
lives here instead:

- `group_kind`: the kind of group; `line` is the standard kind for a survey
  line/traverse, `array` is recommended for station layouts, and other short
  labels are allowed.
- `group_id`: the group's name (same character rules as station IDs).
- `element_kind`: `tx` or `rx` — which table `station_id` refers to.
- `station_id`: the station being assigned; it must exist in `tx.csv` or
  `rx.csv` per `element_kind`.
- `component_id`: leave blank to assign every component at the station, or
  name one component to assign just that one.
- `sequence`: optional order along a `line` (0, 1, 2, ...; gaps allowed);
  leave blank when order is unknown.

`notes.md` is an optional free-text page for provenance and QC narrative —
fill in its headed sections or delete the file.

### Step 6: check and deliver

1. Search the whole folder for `REPLACE` — none may remain.
2. Re-run the spreadsheet export checklist above for every table you touched.
3. Delete this `README.md` (and any unused optional files) from the folder:
   a delivered bundle should contain only the files defined by the spec, and
   validators warn about anything else.
4. Have the bundle validated. If you or a colleague can run Python, the
   reference validator has two help levels: a quick check
   (`python3 tools/validate_csemx.py <your-bundle>`) that needs no extra
   packages, and a complete conformance check (add `--full`) that verifies
   EPSG codes and more but needs a few extra packages
   (`requirements-validation.txt`). No Python is fine too: the manual checks
   above catch the most common mistakes, and sending your first bundle to the
   receiving party for feedback is a normal way to shake out the rest — the
   consumer side can run the validator.
5. Deliver the bundle as a ZIP archive containing this single folder at the
   top level, with the folder renamed for your survey (letters, digits,
   `_`, `.`, `-` only) and ending in `.csemx`, e.g. `mysurvey_2026.csemx.zip`.
