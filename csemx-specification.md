# csemx 1.0 — Specification (DRAFT)

> **Status**: Pre-circulation draft. Subject to revision before any v1.0 freeze.

## 1. Identity and Purpose

- **Name**: `csemx` (controlled-source EM data bundle)
- **Version**: 1.0 (draft)
- **File extension**: `.csemx.zip`
- **MIME type**: `application/vnd.csemx+zip`

A schema-validated, vendor-neutral interchange format for frequency-domain
controlled-source electromagnetic (CSEM) data. A bundle carries **calibrated,
normalized response functions** (§3.6–§3.7), the transmitter and receiver
geometry needed to model them, and the producer's data-quality recommendation
(`use`, §9). It carries no other normative structured payload. (Rationale:
`csemx-rationale.md`.)

It is deliberately **not** a container for:

- **Instrument / vendor internals** — calibration files, coil or electrode
  response curves, gains, serial numbers, or any raw/uncalibrated output.
  Calibration is *applied* before delivery (§3.6), not shipped.
- **Acquisition bookkeeping not needed to model the response** — navigation
  uncertainty, per-sounding timestamps, weather, crew logs.
- **Modeling- or inversion-package settings** — meshes, regularization, error
  floors, starting models, inversion data weighting, or any other consumer-side
  parameter.

Non-normative provenance goes in `notes.md` (bundle-level narrative), `notes`
columns (per-source or per-sensor free text), or `ext_*` extension columns.
Standard readers may ignore `ext_*`, so producers must not place information
required for standard interpretation in `ext_*` columns.

Because all geometry is explicit 3D vertices (wires, loops) or oriented point
elements at arbitrary `(easting, northing, elev)`, one data model covers surface
CSEM, marine towed-dipole, borehole induction logging, and crosswell EM alike:
these differ only in where the vertices sit, not in the schema.

## 2. Bundle Structure

A csemx bundle is a ZIP archive containing a single top-level
directory. The directory name is producer-chosen but must be filesystem-safe
(`[a-zA-Z0-9_.-]+`). Inside that directory, files appear at fixed names:

```
<bundle-name>/
├── manifest.yaml                [required]
├── tx.{csv|parquet}             [required]
├── tx_vertices.{csv|parquet}    [required]
├── rx.{csv|parquet}             [required]
├── rx_vertices.{csv|parquet}    [required]
├── data.{csv|parquet}           [required]
└── notes.md                     [optional]
```

Each table is delivered as **either** `<name>.csv` **or** `<name>.parquet`:
exactly one per table, chosen independently (e.g. small geometry tables as CSV,
a large `data` table as Parquet). A Parquet table holds the same
columns, constraints, and foreign keys (§5–§9) as its CSV form, with the column
types of those sections as Parquet types; missing measurement values are the
native floating-point `NaN` (§3.8). `manifest.yaml` is always YAML.
String ID columns must remain string-typed in Parquet: producers must not let
table writers infer integer types that strip leading zeros (e.g. `001` → `1`).
Floating-point columns must be Parquet `DOUBLE` / float64, not float32, so
coordinate and response precision are preserved.

Every CSV table has a header row naming its columns (RFC 4180); columns are
addressed by name, not by position (Parquet tables carry the same column names
in their schema).

Producers should not include other files inside the bundle directory. Readers
must warn and ignore unknown files there.

## 3. Conventions

All files in a bundle obey these conventions. They are stated here once and
apply globally.

### 3.1 Coordinate System

Declared in `manifest.yaml` under `coordinate_system.epsg_horizontal`: an EPSG
code for a **projected** coordinate reference system (e.g. `32612` = WGS84 / UTM
zone 12N, `32712` = 12S, or any projected national grid). Coordinates are always
**projected `(easting, northing)`, in meters**, the unit for all geometry
operations. The horizontal CRS must use meter axis units; projected CRSs in feet
(for example, State Plane ftUS zones) are invalid.

A geographic (longitude/latitude) CRS such as `4326` is **not** permitted.
Absolute latitude/longitude is recovered by reprojecting `easting`/`northing`
through `epsg_horizontal` and is never stored. A local survey grid must be
reprojected to a projected EPSG CRS before delivery; its original coordinates may
be carried as `ext_*` columns in the vertex tables (§6, §8) or in `notes.md`, but
the projected EPSG geometry is always authoritative. One coordinate system per
bundle.

Write `easting`/`northing`/`elev` with enough decimal places to resolve the
shortest element's orientation, which is the difference of its vertices: a ~1 m
dipole at centimeter precision (2 decimals) fixes azimuth only to ~0.5°, so use
millimeter precision (3 decimals) or finer.

### 3.2 Elevation and Altitude

**Elevation (`elev`, required).** Declared in `manifest.yaml` under
`elevation.epsg_vertical`, an EPSG code defining the height coordinate: `4979`
or a registered vertical CRS with a meter height axis. The two recommended
choices:

- `4979` — WGS84 ellipsoidal height (what GPS/RTK delivers natively); the
  recommended choice. Validators must accept it even though EPSG classifies it as
  a 3D geographic CRS rather than a vertical-only CRS.
- `3855` — EGM2008 geoid; orthometric height ("height above sea level").

Other registered EPSG vertical CRS codes (e.g. a national geoid) are permitted
but discouraged for portability. The `elev` coordinate in every vertex file is
height, **positive up**, in meters, relative to this datum. There is no default;
producers must declare.

**Altitude (`altitude`, optional).** Each vertex may additionally carry
`altitude`: vertical height relative to the local earth-model surface,
**positive up**, in meters, with `0` on the surface. The surface is declared
under `altitude.reference` in `manifest.yaml`:

- `seafloor` — the water–sediment interface (marine).
- `ground` — the air–earth interface (land / airborne).

The surface itself is not part of the bundle; a consumer obtains absolute height
as `altitude` plus the surface height at the vertex in its own model.
`altitude.reference` is required whenever any vertex table includes an
`altitude` column, and absent otherwise.

### 3.3 Azimuth and Dip

- **Azimuth**: degrees, clockwise from true (geographic) north.
  Range `[0, 360)`. All azimuths are true-north; any magnetic-to-true
  declination correction is applied by the producer before delivery and is not
  carried in the bundle (record it in `notes.md` if provenance needs it).
- **Dip**: degrees, positive downward from horizontal. Range `[-90, 90]`.
  A horizontal point axis has `dip=0`; a downward-pointing point axis has
  `dip=+90`.

Azimuth and dip apply only to `point`-geometry transmitters and receivers,
where they give the coil/dipole **axis** as a **directed** unit vector, not an
undirected line. With α = azimuth and δ = dip,

  **n̂** = ( E: cos δ·sin α,  N: cos δ·cos α,  Up: −sin δ ),

so (0°, 0°) points true north, (90°, 0°) east, (0°, +90°) straight down, and
(0°, −90°) straight up. This axis is the element's positive reference direction
(§3.4). The direction *is* the polarity (there is no separate sign field), so
choose azimuth and dip to match the element's positive source/sensor axis. For a
coil, this is the right-hand normal of its winding current. Reversing the
physical leads or sensor polarity negates the response and is corrected before
delivery. For `wire` and `loop` geometries azimuth and dip are forbidden:
orientation is fully encoded in the vertices (§3.4).

### 3.4 Vertex Ordering and Positive Reference Direction

`vertex_index` is 0-based and contiguous per element. Readers sort an element's
vertices by `vertex_index`; file row order is irrelevant. Producers exporting
from 1-based systems must subtract 1 before writing csemx. Each convention
below uses the sorted vertex order: wires use the **first** and **last** vertices,
while loops use the full vertex circulation.

Every element has one **positive reference direction**: a transmitter's source
points along it, and a receiver's datum is taken in that positive sense. It is
fixed by vertex order (wire, loop) or by the directed axis **n̂** of §3.3
(point):

- **Wire (2+ vertices, arbitrary path)** — the positive reference direction
  is **first → last** along the vertex path.
  - *TX:* the impressed electric-current source moment points first → last; the
    first vertex is the **−** sink electrode and the last vertex is the **+**
    injection electrode. This source-moment direction is **−** → **+**, opposite
    the **+** → **−** conduction-current flow through the earth.
  - *RX:* the datum is `∫`**E**·d**l** along the path, first → last (in the
    static/DC limit, where **E** = −∇V, this is
    V(first) − V(last) = V(+) − V(−)); order the vertices so the **first is the
    voltmeter + terminal** and the last the **−**.
- **Loop (TX or RX, closed 3D path)** — the positive sense is the circulation
  through successive vertices in index order; closure from the last vertex back
  to the first is implicit (the first vertex does not repeat). This circulation
  is the authoritative polarity and is not constrained to have an "up" normal.
  For dipole approximations, the loop's oriented area vector is:

  **a** = 1/2 Σ_{i=0}^{N-1} **r_i** × **r_{i+1}**,

  where **r_i** is the 3D position vector `(easting, northing, elev)` in meters
  of vertex `i`, relative to any fixed origin, and **r_N** = **r_0** (closure).
  The closed-loop sum is translation-invariant.
  For a planar loop, **a** = A·**n̂**,
  where **n̂** is the right-hand normal of the circulation. For a non-planar
  loop, **a** is still exactly defined, but using **m** = I·**a** is the dipole
  approximation; the finite-loop geometry remains the closed vertex path.
  - *TX:* conventional source current circulates in the positive sense. The
    finite source is the closed current path; when approximated as a magnetic
    dipole, **m** = I·**a**.
  - *RX:* the datum is `∮`**E**·d**l** around the positive circulation, equal by
    Faraday's law to `−dΦ/dt` through any oriented surface whose boundary
    orientation matches the positive circulation.
- **Point** — exactly one vertex; the positive reference direction is the
  directed axis **+n̂**(azimuth, dip) of §3.3.
  - *TX:* the magnetic moment **m** points along **+n̂**.
  - *RX:* the datum is the projection **B·n̂**, where vector **B** is the per-amp
    magnetic flux density (`T/A`, §3.6) at the vertex and **n̂** is the directed
    axis of §3.3.

The TX-source and RX-positive-datum directions coincide, so a reciprocal Tx/Rx
pair on identical geometry needs no sign flip.

**Geometric validity.** No two consecutive vertices may coincide (within
`1e-6 m`). A loop's first and last vertices must not coincide: closure is
implicit (above), never written explicitly. A loop's edges should not
self-intersect; a self-intersecting loop is physically meaningful but rare, so a
validator warns rather than rejects it.

### 3.5 Sign Convention and Phase Reference

Declared in `manifest.yaml` under `sign.time_dependence`. One of:

- `exp(+iwt)` — engineering convention; positive imaginary part leads in time
- `exp(-iwt)` — physics convention; positive imaginary part lags in time

These are the **exact ASCII values** (lowercase `i`/`w`, explicit sign, no
spaces); a validator rejects any other string.

No default. Producers must declare. Readers consuming multiple bundles with
different conventions must flip the sign of the imaginary part when
normalizing to an internal convention.

**Phase reference.** The complex response (`real`, `imag` in the `data` table)
must be delivered in phase relative to the transmitter current spectral
component at the reported `frequency`. If acquisition or processing uses a
different internal reference (lock-in phase, GPS time, transmitter voltage, or a
reference-clock phase), the producer must correct the delivered response to this
current reference before writing the bundle. Beyond this current-reference
conversion, no propagation-time correction or additional timing convention is
represented in the bundle.

### 3.6 Units and the Measured Datum

Each `data` table row carries a complex **response**: the receiver's measured
quantity, normalized by the transmitter drive (§3.7). The datum type is
determined by the receiver **`geometry_type`**: wire and loop receivers report
voltage responses, while point (magnetic) receivers report B-field responses.

**Units are fixed by this specification; they are not carried in the bundle.**
csemx is a final processed delivery format: every value is in the canonical unit
for its quantity *before* delivery (§3.7). Because every unit is fixed here, no
manifest field declares or selects units, and bundles never require unit
reconciliation. All quantities are **canonical SI**: no SI prefixes
(`mV`, `nT`, `km`), no Unicode operators
(`V/(A·m²)`), no scalar multipliers, and no alternate spellings.

**Response datum.** The `data` table `real`/`imag` (and the `err_real`/`err_imag`
that share each row) carry the response; its unit follows from the receiver
`geometry_type`. By default the response is the **total** field; a bundle may
instead deliver the **secondary** field (total minus the free-space primary) by
declaring `field.content: secondary` (§3.11), which changes what `real`/`imag`
mean but not their unit:

| receiver `geometry_type` | datum                                  | unit  |
| ------------------------ | -------------------------------------- | ----- |
| `wire` (electric)        | open-path voltage per TX amp           | `V/A` |
| `loop` (magnetic)        | single-turn closed-loop EMF per TX amp | `V/A` |
| `point` (magnetic)       | B-field flux density per TX amp        | `T/A` |

Error columns `err_real`/`err_imag` (§9) have no unit of their own: each
inherits the unit of the datum in its row.

**All other quantities** carry a fixed unit too, stated at each column's point of
use and collected here for reference:

| quantity                      | unit                   | defined in   |
| ----------------------------- | ---------------------- | ------------ |
| `easting`, `northing`         | meter (m)              | §3.1, §6, §8 |
| `elev`                        | meter (m), positive up | §3.2, §6, §8 |
| `altitude`                    | meter (m), positive up | §3.2, §6, §8 |
| `azimuth_deg`                 | degree (°)             | §3.3, §5, §7 |
| `dip_deg`                     | degree (°)             | §3.3, §5, §7 |
| `frequency`, `tx_fundamental` | hertz (Hz)             | §9           |
| `point_moment_area_m2`        | square meter (m²)      | §5           |

There is deliberately **no** `length` or `current` unit to declare: coordinates
are meters, current is normalized away (§3.7), and the one area column carries
its unit in its name (`point_moment_area_m2`, §5).

### 3.7 Normalization

Every response is normalized so it depends on the earth and the survey
geometry, not on how hard the transmitter was driven. There is no
un-normalized form; normalize before writing the bundle.

- **By current (all sources).** Divide the measured quantity by the complex
  transmitter-current spectral component (Fourier coefficient / phasor) at the
  measurement `frequency`, using the same Fourier normalization as the measured
  response, to yield the per-amp response of §3.6 (`V/A` or `T/A`). For a
  multi-frequency or encoded drive this is the current component being reported —
  not a nominal waveform peak and not an RMS value — so each reported frequency is
  normalized by its own current component.
- **By turns (`loop`/`point` sources only).** A `loop` or `point` source's moment
  scales with `N`, current, and single-turn area vector. These responses are
  *additionally* divided by the turn count `N`, so the stored value
  corresponds to a **single-turn** source. The source's spatial extent and vector
  area are carried by its `loop` geometry, or, for a `point`, by
  `point_moment_area_m2` (§5). `N` is consumed here and appears in no column —
  record it in `tx.notes` or `notes.md` if provenance needs it.
- **By receiver turns (loop receivers only).** A loop receiver's induced EMF is
  proportional to its turn count. Loop-receiver responses are divided by the
  receiver turn count `N`, so the stored value corresponds to a **single-turn**
  receiver loop. The loop path and vector area remain in the `rx_vertices` table.
  Record receiver `N` in `rx.notes` or `notes.md` if provenance needs it.

### 3.8 Missing Values

A missing measurement value is `NaN`. In a CSV table producers write `NaN` and
readers must accept it case-insensitively (`NaN`/`nan`/`NAN`); in a Parquet table
it is the native floating-point `NaN`. There is no configurable sentinel.

`NaN` is valid only in the `data` table measurement columns (`real`, `imag`,
`err_real`, `err_imag`), under the all-or-nothing rule of §9. Required
non-measurement fields must carry a non-blank, non-`NaN` value. Optional or
conditionally not-applicable fields may be empty in CSV, or null in Parquet,
when omitted for that row; emptiness is not a measurement-missing sentinel.

### 3.9 Component Naming

A component ID (`rx_component_id` or `tx_component_id`) is an **opaque,
case-sensitive label** matching `[A-Za-z0-9_-]{1,32}`. It is a join key: it must
match exactly between the corresponding element table (`tx` or `rx`), its vertex
table, and `data` rows that reference it.

**Orientation is never read from a label.** A label is a stable join/grouping
key, not a promise of direction: the format never defines what an `Ex` points
at, the same name may point differently at two stations, and `x`/`y`/`z` never
denote the global `easting`/`northing`/`elev` axes. To select or group channels
*by orientation* (e.g. every near-inline dipole), use `azimuth_deg`/`dip_deg`
(`point`) or the vertices (`wire`/`loop`), which are exact, per-channel, and
survive reprojection.

**Receivers** have a conventional vocabulary, used where it genuinely applies:
`Ex`/`Ey`/`Ez` (electric) and `Bx`/`By`/`Bz` (magnetic; always `B` labels, never
a separate `H` set). It is recommended, not required: a non-orthogonal or
grid-relative layout may use a clearer label such as `Einline` or `Ecross`.
When one of these exact conventional IDs is used, `geometry_type` must be
consistent with it: `Ex`/`Ey`/`Ez` require `wire`, and `Bx`/`By`/`Bz` require
`point` (a `loop` receiver reports EMF in `V/A`, not a point B-component, so it
takes a distinct label such as `Bloop`). A channel's field type is always derived
from `geometry_type` (§3.10), for conventional and custom labels alike, never
from the label.

**Transmitters** have **no** conventional set; source elements are labeled at
the producer's discretion (e.g. `E1`, `E2`, or descriptive names). A tensor
source's elements share one `tx_station_id` with distinct `tx_component_id`s.

### 3.10 Geometry and Field Type

Geometry represents the acquisition element: finite wires/loops as vertices,
small magnetic coils as oriented points. `geometry_type` is the stored
discriminator; the physical field type (electric vs magnetic) is **derived** from
it, not stored:

| `geometry_type` | field type | element                                              |
| --------------- | ---------- | ---------------------------------------------------- |
| `wire`          | electric   | an electric dipole (grounded or capacitive); length & shape from vertices |
| `loop`          | magnetic   | a closed loop source/receiver; path and vector area from vertices |
| `point`         | magnetic   | a point magnetic dipole/coil; axis, plus area for TX points |

So **`wire ⟹ electric`** and **`loop | point ⟹ magnetic`**. There is no electric
loop or magnetic wire, and no electric point: csemx represents electric data as
open-path wire voltages/line integrals over finite baselines. A `point`
is always magnetic and carries `azimuth_deg`/`dip_deg` for its axis; a `point`
magnetic **transmitter** additionally carries `point_moment_area_m2`, while a
`point` magnetic **receiver** and any `loop` carry no further columns. The datum
unit follows from `geometry_type` (§3.6), not from the field type: a `loop` and a
`point` are both magnetic but report `V/A` and `T/A`.

### 3.11 Field Content: Total or Secondary

By default `real`/`imag` carry the **total** per-amp response (§3.6). A bundle may
instead carry the **secondary** response by declaring in `manifest.yaml`:

```yaml
field:
  content: secondary # total | secondary
```

When the `field` block is absent, `content` is `total` and every value is the
total field. When `content` is `secondary`, `real`/`imag` carry the total field
minus the **free-space primary** in the same `V/A`/`T/A` unit (§3.6). The primary
is needed only to define secondary response and recover total response; no
primary value is stored in the bundle.

**Primary field.** For secondary-field bundles, readers compute the primary from
the encoded transmitter and receiver geometry: the response the transmitter
would produce at the receiver in a non-conducting whole space, taken in the
receiver's positive datum sense (§3.4). For a `point`→`point` pair it is the
analytic dipole field of `point_moment_area_m2` at the transmitter vertex,
evaluated at the receiver vertex and projected on the receiver axis **n̂**; for
finite `wire`/`loop` elements it is the corresponding free-space line or loop
integral.

Its phase depends on the receiver datum. For a `point` (B-field, `T/A`) receiver
the primary is in phase with the transmitter current, so it is **real** under
either sign convention (§3.5) and removing it changes only the in-phase part. For a
`loop` (EMF, `V/A`) receiver the datum is `−dΦ/dt`, so the free-space primary is in
quadrature with the current (`−iωΦ` under `exp(+iwt)`, `+iωΦ` under `exp(-iwt)`,
where `Φ` is the free-space flux per amp through the loop). Removing it changes
the quadrature part. For `wire` receiver rows, the primary is the corresponding
free-space electric line integral for the encoded source geometry and sign
convention.

**Recovering total.** For secondary-field bundles, consumers recover the total
response as `total = secondary + primary`, with `primary` computed as above. ppm
is not stored; if needed for display or comparison with legacy FDEM deliveries,
it is derived outside the csemx datum.

`field.content` applies to the whole bundle.

## 4. File: `manifest.yaml`

```yaml
format:
  name: csemx
  version: "1.0"

domain: frequency # v1.0 defines only `frequency`

survey:
  name: "Example Survey"
  revision: 1 # integer, incremented per re-ship; higher = newer
  acquired_start: "2026-02-28" # quoted date or UTC timestamp; see rules below
  acquired_end: "2026-03-15" # same precision as acquired_start; may equal start
  contractor: "Synthetic Producer" # required; part of re-ship identity
  contractor_reference: "Example 26011" # required; part of re-ship identity

coordinate_system:
  epsg_horizontal: 32615 # projected EPSG code; here WGS84 / UTM zone 15N (Gulf of Mexico, marine)

elevation:
  epsg_vertical: 4979 # required: vertical coordinate code (§3.2)

altitude: # optional (§3.2); required only if a vertex table has an `altitude` column
  reference: seafloor # seafloor | ground

sign:
  time_dependence: "exp(+iwt)" # exp(+iwt) | exp(-iwt)

field: # optional (§3.11); absent ⇒ content: total
  content: total # total | secondary
```

All keys above are required unless noted. v1.0 defines only
`domain: frequency`; readers that implement only v1.0 reject any other domain.
Bundle-level free-form contractor notes belong in `notes.md` (§10), not in the
manifest.

The `survey` mapping has the following required keys:

| key                    | type                 | constraint |
| ---------------------- | -------------------- | ---------- |
| `name`                 | string               | non-blank survey name |
| `revision`             | integer              | `>= 1`; incremented for corrected re-ships |
| `acquired_start`       | acquisition endpoint | exact grammar below |
| `acquired_end`         | acquisition endpoint | exact grammar below; `>= acquired_start` |
| `contractor`           | string               | non-blank producer name |
| `contractor_reference` | string               | non-blank producer job/contract/reference ID |

`survey.acquired_start` and `survey.acquired_end` are the acquisition interval
endpoints. Each value must be exactly one of:

- Date-only: `YYYY-MM-DD`
- UTC timestamp: `YYYY-MM-DDTHH:MM:SSZ`

Both are written as quoted strings (e.g. `"2026-05-01"`); an unquoted YAML date
parses as a date object, not a string, and is rejected.

Both endpoints must use the same precision: either both date-only or both UTC
timestamps. `survey.acquired_end` must be on or after `survey.acquired_start`.
UTC timestamps use literal trailing `Z`; timezone offsets, local times,
fractional seconds, partial times, slashes, month names, and free text are
invalid. Date-only values are day-level acquisition bounds, not implied
local-midnight instants.

**Bundle composition and re-ships.** A bundle is self-contained: all `data`
foreign keys resolve within it. A survey identity is
`(contractor, contractor_reference, survey.name)`. One survey may be delivered
as multiple bundles or re-shipped. Across bundles with the same survey identity,
a datum key is the §9 uniqueness tuple
`(tx_station_id, tx_component_id, rx_station_id, rx_component_id, frequency)`.
If the same datum key appears in more than one bundle, the row from the highest
`survey.revision` supersedes the others; if the same datum key appears more than
once at the same `survey.revision`, the survey delivery is ambiguous and
non-conformant.

## 5. File: `tx.csv`

One row per transmitter element: one `(tx_station_id, tx_component_id)` pair.
CSV (UTF-8, RFC 4180) or Parquet, per §2.

A `tx_station_id` groups one or more co-located source elements, each identified
by a `tx_component_id` (e.g. the two crossed bipoles of a tensor source).
Orientation comes from geometry, not the label (§3.9).

### Required columns

| column            | type   | constraint                                  |
| ----------------- | ------ | ------------------------------------------- |
| `tx_station_id`   | string | `[A-Za-z0-9_-]{1,64}`                       |
| `tx_component_id` | string | source-element label; `[A-Za-z0-9_-]{1,32}` |
| `geometry_type`   | enum   | `point` \| `wire` \| `loop`                 |

`(tx_station_id, tx_component_id)` is the unique key.

Geometry follows §3.10; a `point` transmitter is therefore always magnetic.

### Conditionally required

| column                 | required when         | type  | constraint                                            |
| ---------------------- | --------------------- | ----- | ----------------------------------------------------- |
| `azimuth_deg`          | `geometry_type=point` | float | `[0, 360)`; positive source axis                      |
| `dip_deg`              | `geometry_type=point` | float | `[-90, 90]`; positive source axis                     |
| `point_moment_area_m2` | `geometry_type=point` | float | `> 0`; effective single-turn moment area `A` (m²)     |

`point_moment_area_m2` is the point coil's effective single-turn area, not
`N·A`; turns are normalized out (§3.7). It is required only for point
transmitters because they have no vertices from which to compute loop area.

### Optional

| column  | type   | purpose                                        |
| ------- | ------ | ---------------------------------------------- |
| `notes` | string | free text about this source element; max 1024 characters |
| `ext_*` | any    | producer-specific extension columns; not required for standard interpretation |

## 6. File: `tx_vertices.csv`

One row per vertex. Required columns:

| column            | type   | constraint                                        |
| ----------------- | ------ | ------------------------------------------------- |
| `tx_station_id`   | string | FK to `tx.csv.tx_station_id`                      |
| `tx_component_id` | string | FK (joint with `tx_station_id`)                   |
| `vertex_index`    | int    | contiguous ordering key, 0-based per element (§3.4) |
| `easting`         | float  | meters, per `coordinate_system`                   |
| `northing`        | float  | meters, per `coordinate_system`                   |
| `elev`            | float  | height, positive up, meters, per `elevation`      |

Optional columns:

| column     | type | purpose                                                                       |
| ---------- | ---- | ----------------------------------------------------------------------------- |
| `altitude` | float | meters, positive up; vertical height relative to the local earth-model surface declared by `altitude.reference` (§3.2) |
| `ext_*`    | any  | producer-specific extension columns; not required for standard interpretation |

The `ext_*` columns may carry per-vertex provenance, e.g. each vertex's original
local-grid coordinates `ext_grid_x`/`ext_grid_y` alongside the projected
`easting`/`northing` (§3.1).

`(tx_station_id, tx_component_id, vertex_index)` must be unique. Vertex count
per `(tx_station_id, tx_component_id)`:

- `point`: exactly 1
- `wire`: ≥ 2
- `loop`: ≥ 3

## 7. File: `rx.csv`

One row per `(rx_station_id, rx_component_id)` pair. CSV (UTF-8, RFC 4180) or Parquet, per §2.

### Required columns

| column            | type   | constraint                                                           |
| ----------------- | ------ | ------------------------------------------------------------------- |
| `rx_station_id`   | string | `[A-Za-z0-9_-]{1,64}`                                               |
| `rx_component_id` | string | `[A-Za-z0-9_-]{1,32}` (§3.9); conventional `Ex`/`Ey`/`Ez`/`Bx`/`By`/`Bz` |
| `geometry_type`   | enum   | `point` \| `wire` \| `loop`                                         |

`(rx_station_id, rx_component_id)` is the unique key. A channel's field type
(electric/magnetic) is derived from `geometry_type` (§3.10), never declared
separately. Conventional IDs must be consistent with geometry: `Ex`/`Ey`/`Ez`
require `wire`; `Bx`/`By`/`Bz` require `point` (§3.9).

Geometry follows §3.10. `point` and `loop` receivers carry **no** moment column;
the datum is already calibrated (B-field for `point`, loop EMF for `loop`), units
per §3.6.

### Conditionally required

| column        | required when         | type  | constraint                        |
| ------------- | --------------------- | ----- | --------------------------------- |
| `azimuth_deg` | `geometry_type=point` | float | `[0, 360)`; positive sensor axis  |
| `dip_deg`     | `geometry_type=point` | float | `[-90, 90]`; positive sensor axis |

### Optional

| column  | type   | purpose                                        |
| ------- | ------ | ---------------------------------------------- |
| `notes` | string | free text about this sensor element; max 1024 characters |
| `ext_*` | any    | producer-specific extension columns; not required for standard interpretation |

## 8. File: `rx_vertices.csv`

One row per receiver vertex. Required columns:

| column            | type   | constraint                                   |
| ----------------- | ------ | -------------------------------------------- |
| `rx_station_id`   | string | FK to `rx.csv.rx_station_id`                 |
| `rx_component_id` | string | FK (joint with `rx_station_id`)              |
| `vertex_index`    | int    | contiguous ordering key, 0-based per element (§3.4) |
| `easting`         | float  | meters, per `coordinate_system`              |
| `northing`        | float  | meters, per `coordinate_system`              |
| `elev`            | float  | height, positive up, meters, per `elevation` |

Optional columns `altitude` (§3.2) and `ext_*` extension columns, exactly as for
`tx_vertices` (§6).

`(rx_station_id, rx_component_id, vertex_index)` must be unique. Vertex count
per `(rx_station_id, rx_component_id)`:

- `point`: exactly 1
- `wire`: ≥ 2
- `loop`: ≥ 3

## 9. File: `data.csv`

One row per measurement. CSV (UTF-8, RFC 4180) or Parquet, per §2.

### Required columns (always)

| column            | type   | constraint                         |
| ----------------- | ------ | ---------------------------------- |
| `tx_station_id`   | string | FK to `tx.csv.tx_station_id`       |
| `tx_component_id` | string | FK (joint with `tx_station_id`)    |
| `rx_station_id`   | string | FK to `rx.csv.rx_station_id`       |
| `rx_component_id` | string | FK (joint with `rx_station_id`)    |
| `frequency`       | float  | `> 0`; in Hz                       |
| `real`            | float  | real part of complex response      |
| `imag`            | float  | imaginary part of complex response |
| `err_real`        | float  | absolute error on real part; `≥ 0` |
| `err_imag`        | float  | absolute error on imag part; `≥ 0` |

### Optional

| column           | type           | purpose                                                 |
| ---------------- | -------------- | ------------------------------------------------------- |
| `tx_fundamental` | positive float | transmitter drive nominal repetition/fundamental (Hz)   |
| `use`            | integer        | `0` or `1`; defaults to `1` when omitted                |
| `ext_*`          | any            | producer-specific extension columns; not required for standard interpretation |

If `use` is present, every row must contain `0` or `1`; blank values are invalid.

### Empty handling

Missing measurement values are `NaN`, never blank or null (§3.8).

A complex datum is **all-or-nothing**: either both `real` and `imag` are finite
(a present datum), or both are `NaN` (a missing datum: attempted but no usable
result; consumers may skip it). One present and the other `NaN` is invalid.
**Errors follow the datum**: a present datum requires finite `err_real`/`err_imag`
(`≥ 0`); a missing datum requires `NaN` in `err_real`/`err_imag` too. A finite or
zero error on a missing datum is invalid.

A present datum the producer considers unreliable but must still deliver (e.g.
contractual completeness) is marked `use = 0`, not omitted, and not given an
inflated error. Its `real`/`imag` and errors remain the true measured values;
`use` carries the quality judgment separately. The flag is advisory; consumers
may override it.

Uniqueness: `(tx_station_id, tx_component_id, rx_station_id, rx_component_id,
frequency)` must be unique. Duplicate rows are invalid.

`tx_fundamental` is optional provenance, not part of the key. It is not
constrained to match `frequency`; omit it when not meaningful. The response at a
given `frequency` is one physical quantity regardless of the exciting waveform.

The `data` table is the producer's selected processed dataset for modeling. If a
producer wants to deliver alternate stacks, trial processing runs, or other
non-superseding realizations of the same datum, those should be shipped as
separate csemx bundles and described in `notes.md`; they are not represented as
parallel rows in one bundle.

## 10. File: `notes.md` (optional)

Free-form contractor-authored markdown for bundle-level narrative. No schema.
May summarize non-normative instrument provenance, processing history,
contractor QC notes, and acknowledgments, but must not carry information required
to interpret or calibrate the data.
Readers must not interpret its contents programmatically.

## 11. Versioning

- Spec version is the exact string `MAJOR.MINOR`, declared in `format.version`.
  The v1.0 manifest schema accepts exactly `format.version: "1.0"`.
- Within a major version, changes are additive: new optional columns, new
  optional manifest keys, new optional files. Readers handling `MAJOR.X`
  must accept any `MAJOR.Y` bundle (for Y ≤ X) and ignore unknown additions.
- The `domain` key is the exception to "ignore unknown additions": each domain
  defines its own data model, so a reader rejects — rather than ignores — a
  `domain` it does not implement (§4).
- Breaking changes increment `MAJOR`. A `2.x` reader is not required to
  read `1.x` bundles.
- Producers must write the exact spec version they target. Readers must
  verify `format.name == "csemx"` and `format.version` major matches a
  supported version.

## 12. Worked Example

A representative bundle exercising every geometry flavor: a grounded-wire
electric transmitter (`TX01`), a surface loop transmitter (`TX02`), a borehole
point-magnetic transmitter (`BH1`), and one receiver station (`001`) with
electric dipoles, point magnetic coils, and a finite magnetic loop receiver.

`manifest.yaml`:

```yaml
format: { name: csemx, version: "1.0" }
domain: frequency
survey:
  name: "Example"
  revision: 1
  acquired_start: "2026-05-01T14:32:00Z"
  acquired_end: "2026-05-01T18:47:00Z"
  contractor: "Synthetic Producer"
  contractor_reference: "Example 0001"
coordinate_system: { epsg_horizontal: 32612 } # WGS84 / UTM 12N (onshore Arizona, land)
elevation: { epsg_vertical: 4979 }            # WGS84 ellipsoidal
sign: { time_dependence: "exp(+iwt)" }
```

`tx.csv`: `point_moment_area_m2` is filled only for the borehole point
source; the wire and loop leave it (and azimuth/dip) blank:

```csv
tx_station_id,tx_component_id,geometry_type,azimuth_deg,dip_deg,point_moment_area_m2
TX01,E1,wire,,,
TX02,M1,loop,,,
BH1,M1,point,0,90,0.0079
```

`tx_vertices.csv`: wire = 2 electrodes, loop = closed polygon (closure
implicit), borehole point = a single vertex at depth:

```csv
tx_station_id,tx_component_id,vertex_index,easting,northing,elev
TX01,E1,0,554252.03,3626434.36,1849.10
TX01,E1,1,554648.70,3626426.20,1899.21
TX02,M1,0,556000.00,3628000.00,1805.00
TX02,M1,1,556100.00,3628000.00,1805.50
TX02,M1,2,556100.00,3628100.00,1806.00
TX02,M1,3,556000.00,3628100.00,1805.50
BH1,M1,0,556000.00,3628000.00,1000.00
```

`rx.csv`: electric channels are wires (azimuth/dip blank); magnetic
point channels are point coils (axis in azimuth/dip); the magnetic loop receiver
is a closed voltage receiver. No moment column appears for receivers:

```csv
rx_station_id,rx_component_id,geometry_type,azimuth_deg,dip_deg
001,Ex,wire,,
001,Ey,wire,,
001,Bx,point,0,0
001,By,point,90,0
001,Bz,point,0,90
001,Bloop,loop,,
```

`rx_vertices.csv`: dipoles have 2 vertices; the three point coils are
co-located at the magnetometer point; the loop has four vertices with implicit
closure:

```csv
rx_station_id,rx_component_id,vertex_index,easting,northing,elev
001,Ex,0,551100.00,3625900.00,1460.00
001,Ex,1,551200.00,3625900.00,1461.00
001,Ey,0,551150.00,3625850.00,1460.50
001,Ey,1,551150.00,3625950.00,1460.50
001,Bx,0,551150.00,3625900.00,1460.00
001,By,0,551150.00,3625900.00,1460.00
001,Bz,0,551150.00,3625900.00,1460.00
001,Bloop,0,551130.00,3625880.00,1460.00
001,Bloop,1,551170.00,3625880.00,1460.00
001,Bloop,2,551170.00,3625920.00,1460.00
001,Bloop,3,551130.00,3625920.00,1460.00
```

`data.csv`: wire and loop receiver rows are `V/A`; point magnetic receiver
rows are `T/A` (per §3.6):

```csv
tx_station_id,tx_component_id,rx_station_id,rx_component_id,frequency,real,imag,err_real,err_imag
TX01,E1,001,Ex,0.125,2.14e-6,-3.10e-7,3.0e-8,2.8e-8
TX01,E1,001,Ey,0.125,8.40e-7,-1.20e-7,2.0e-8,2.1e-8
TX01,E1,001,Bz,0.125,5.30e-12,-9.10e-13,1.1e-13,1.0e-13
TX01,E1,001,Bloop,0.125,-1.10e-9,-6.70e-9,1.2e-10,1.1e-10
TX02,M1,001,Bz,0.125,7.80e-11,-1.40e-11,9.0e-13,8.5e-13
BH1,M1,001,Bz,0.125,3.20e-11,-5.50e-12,4.0e-13,3.8e-13
```

## 13. References

This spec is text-based and built on widely-supported standards, so conforming
readers and writers can be assembled from existing libraries rather than
written from scratch.

**Underlying formats (normative).** A conforming bundle is valid against these:

- CSV: [RFC 4180](https://www.rfc-editor.org/rfc/rfc4180)
- Parquet: [Apache Parquet format](https://parquet.apache.org/docs/file-format/)
- YAML: [YAML 1.2](https://yaml.org/spec/1.2.2/)
- Manifest schema: csemx manifest schema, expressed as
  [JSON Schema](https://json-schema.org/)

**Coordinate / CRS handling (EPSG).** Every horizontal and vertical reference
system is an EPSG code; the registry and tooling are mature:

- EPSG Geodetic Parameter Dataset (IOGP — the authority): <https://epsg.org>
- Lookup / convenience tool: <https://epsg.io>
- Common codes: `32612` / `32712` (WGS84 / UTM 12N / 12S, projected meters —
  the kind of code required for `epsg_horizontal`), `4979` (WGS84 ellipsoidal
  height), `3855` (EGM2008 geoid). `4326` (WGS84 geographic) is shown by tools
  but is **not** a valid `epsg_horizontal` here — positions are projected
  meters only.
- Python: [`pyproj`](https://pyproj4.github.io/pyproj/) (PROJ bindings) for
  CRS definitions, reprojection, and axis-order handling.
- Rust: [`proj`](https://crates.io/crates/proj) (PROJ bindings) or
  [`proj4rs`](https://crates.io/crates/proj4rs) (pure Rust).

**Bundle parsing:**

- Python: `csv` or `pandas` for CSV tables, `pyarrow` for Parquet tables,
  `pyyaml` for the manifest, `jsonschema` for the manifest schema; optionally
  [`frictionless`](https://framework.frictionlessdata.io/) if validation is
  driven from a Table Schema. Because `acquired_start`/`acquired_end` are quoted
  strings in the manifest, a standard YAML load yields strings and the schema
  validates with no special loader.
- Rust: `csv`, `serde_yaml`.
