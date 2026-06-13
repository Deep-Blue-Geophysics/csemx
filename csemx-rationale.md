# csemx — Design Rationale (companion to the spec)

Companion to `csemx-specification.md`. The spec states the rules tersely; this
records the *why* behind each non-obvious decision, so a reader who questions a
rule there can find its justification here. Sections follow the spec where a
rationale is useful; purely tabular field definitions are omitted.

## §1 Scope and configurations

**One data model for every configuration.** Geometry is always explicit 3D
vertices (wires, loops) or oriented point elements at arbitrary
`(easting, northing, elev)`. Surface CSEM, marine towed-dipole, borehole
induction, and crosswell EM then differ only in where the vertices sit and
whether an element is a wire or a coil: no per-configuration schema, no
special-case objects.

**Moving sources/receivers are dense station sequences.** A towed source (and
possibly receiver) moves continuously, so each position is its own
`tx_station_id`/`rx_station_id`. A dense sequence of single-use stations is the
*intended* idiom: a tow line is not an object the schema must model specially.

**Calibrated response only.** The normative payload is the geometry needed to
model the response, the calibrated normalized response functions, and the
producer's `use` recommendation, and nothing else. Instrument internals
(calibration curves, gains, serial numbers) are applied before delivery;
acquisition bookkeeping (navigation uncertainty, weather, crew logs) and
consumer-side modeling/inversion settings are not properties of the EM response.
Environmental/medium properties (seawater conductivity, CTD profiles, borehole
fluids) are modeling inputs and ship separately.

## §2 Bundle structure: ZIP + CSV/Parquet, not HDF5/SQLite

**ZIP of fixed-name tables.** A bundle is a ZIP of one directory with fixed
filenames, so a reader locates every table without configuration. The `.zip`
already supplies the single-self-describing-file property, leaving a
human-readable YAML manifest rather than an opaque container header.

**Geometry split from elements.** Element metadata (`tx`/`rx`) is separated from
geometry (`*_vertices`), joined by keys, because vertex count varies per element
(point = 1, wire ≥ 2, loop ≥ 3) and does not fit a fixed-width element row. The
split also lets a large vertex table go to Parquet on its own.

**Parquet per table, chosen over HDF5/SQLite on contractor-straightforwardness.**
Airborne/marine volume bloats not just `data` but `tx`/`rx` and their vertex
tables, so binarization must be available per table, not just for `data`.

- Parquet *is* the typed table — its schema is the column set the spec already
  defines, so whoever writes the CSV can write Parquet with a single library call
  in common analysis tools. Minimal structural ambiguity, little room for
  per-vendor divergence.
- HDF5 is a flexible *container*, not a schema: using it would require pinning an
  internal group/dataset layout each contractor must build correctly —
  reintroducing the per-file divergence csemx exists to remove — with a fiddlier
  API and portability quirks; tables are not its native idiom.
- SQLite is a database container rather than a plain table exchange format; using
  it would add database-specific implementation choices without matching the
  fixed-file export path most producers already have.

Per-table choice keeps small geometry tables readable as CSV while a large `data`
table goes binary. Parquet stores real float `NaN` and required f64 values,
avoiding CSV `NaN`-casing issues and preserving the precision producers write.
String IDs must stay string-typed: a writer that infers `001` → `1` silently
corrupts join keys.

## §3.1 Coordinate system

A single EPSG code pins projection, datum, axis order, and units unambiguously
and is understood by standard geospatial tooling. A geographic CRS (degrees, e.g.
`4326`) breaks the geometry conventions: §3.4 takes lengths and orientations as
Euclidean differences of vertex coordinates, but degree spacing is non-uniform
and latitude-dependent (1° longitude ≈ 111 km·cos φ), so those differences are
not metric; projected meter-axis coordinates are required. Feet are rejected
because they would silently corrupt lengths and areas. Absolute lat/lon is
recovered by reprojecting `easting`/`northing` through `epsg_horizontal` and is
never stored, so there is no second copy to drift out of sync.

**No local grid.** A producer using a private origin/rotation already holds the
georeferencing needed to reproject into a registered projected CRS before
delivery. Requiring a registered code keeps every bundle readable by standard
tooling and free of bespoke frame parameters. Original local-grid coordinates may
ride along as ignored `ext_*` provenance or be described in `notes.md`, but are
never the authoritative geometry.

## §3.2 Elevation and altitude

**Elevation datum is declared, never defaulted.** A silent default would let two
producers mean different surfaces by the same number. `4979` (WGS84 ellipsoidal)
is the recommended choice because GPS/RTK delivers ellipsoidal height natively:
zero geoid conversion, no model dependence; `3855` (EGM2008 orthometric) is
offered for "height above sea level" when that is what was recorded.

**Altitude is the optional, interface-relative companion.** Marine CSEM (and
airborne EM) response is acutely sensitive to instrument **height above the
interface** (seafloor or ground), which the altimeter measures directly.
Absolute elevation captures it poorly: bathymetry/DEM grids disagree in absolute
z by meters (datum, tides, resolution), so computing
`altitude = elev − surface(x,y)` lands that disagreement on the most sensitive
parameter. Carrying the measured `altitude` lets a consumer place each vertex at
the right height above *their own model's* interface without baking in the
producer's bathymetry/DEM. `elev` remains the required absolute height for
mapping, exchange, and downhole geometry; `altitude` is an optional
interface-relative placement aid, not a second vertical datum. The reference
surface itself is not shipped (topo/bathy is a modeling input, out of scope);
`altitude.reference` only names the interface (`seafloor`/`ground`).

## §3.3 Azimuth and dip

**Direction *is* polarity.** A point element's azimuth/dip give a *directed*
axis **n̂**, and that direction carries the source/sensor sign. There is no
separate polarity field. Folding sign into the axis removes a redundant flag
that could contradict the geometry: the producer picks azimuth/dip to match the
element's positive source or sensor axis. For a coil, that is the right-hand
normal of its winding current; reversed leads or sensor polarity are corrected
before delivery, not represented by a sign column.

**True north, dip positive down.** Azimuths are true-north because magnetic
declination varies in time and space and is a producer correction, not survey
data (record it in `notes.md` if provenance needs it). Dip is positive downward,
following the standard geophysical convention that inclination into the earth is
positive.

**Forbidden on wire/loop.** Vertex order already fixes a wire's or loop's
orientation, so azimuth/dip there would be a second encoding of the same fact,
and two encodings invite contradiction.

## §3.4 Vertex ordering and positive reference direction

**RX wire / bent wire.** At nonzero CSEM frequency **E** is generally
non-conservative (∇×**E** = −∂**B**/∂t), so a wire receiver's datum is the line
integral along its stated path, not a path-independent endpoint potential. In
the DC/static limit this reduces to the familiar `V(+) − V(−)` convention. csemx
orders the RX wire so the **first** vertex is the voltmeter **+** terminal and the
**last** the **−**, so the datum is `∫E·dl` taken along the vertex path (first →
last) with no sign flip.

**Loop circulation and vector area.** The loop's signed circulation is *derived*
from vertex order and is never constrained to have an "up" normal, which keeps the
convention lossless for real non-planar loops on topography. For dipole
approximations csemx uses the oriented area vector
**a** = ½ Σ_{i=0}^{N-1} **r_i** × **r_{i+1}** (with **r_N** = **r_0**), where
**r_i** is the 3D position of vertex `i` relative to any fixed origin; the
closed-loop sum is translation-invariant. For a planar loop this reduces to
A·**n̂** with **n̂** from the right-hand rule; for a non-planar loop **a** is still
exact, but **m** = I·**a** is then the dipole approximation and the finite-loop
geometry remains the closed vertex path.

**TX vs RX electrode order (one positive sense).** Both TX and RX take the vertex
order, first → last, as the positive reference direction, so a reciprocal Tx/Rx
pair on identical geometry needs no sign flip. The electrode labels that realize
this are opposite: a TX dipole moment points − to + (first → last is − → +, the
impressed source-current direction, *not* the earth-conduction-current direction,
which runs + → − through the earth), whereas an RX wire reads `V(+) − V(−)`, so
its **+** terminal is the **first** vertex.

## §3.5 Sign convention and phase reference

**Both conventions are declared, not mandated.** `exp(+iwt)` (engineering) and
`exp(-iwt)` (physics) are both in active use; mandating one would force every
producer or consumer on the other side to convert. csemx declares the convention
so a multi-bundle consumer flips the imaginary sign once, at ingest. No default:
a wrong-but-present default is more dangerous than a required field because it is
silently plausible.

**Phase referenced to the transmitter current.** The response is delivered in
phase relative to the transmitter-current spectral component at `frequency`, so it
is comparable across instruments regardless of the internal reference used during
acquisition (lock-in phase, GPS time, transmitter voltage, reference clock). The
producer converts to this reference before delivery. No propagation-time
correction is represented. That is a modeling step, not a property of the
measurement.

## §3.6 Units and the measured datum

Wire/loop receiver responses are kept at `V/A` (not divided by dipole length or
loop vector area) because the length, shape, polarity, and winding sense are
already in `rx_vertices.csv`; a modeling code computes the datum as the
appropriate line integral of **E**: open-path `∫E·dl` along the wire's vertex
path for a wire, closed-loop `∮E·dl` for a loop. A point magnetic receiver reports
a calibrated projected B-field, so `T/A` is already the natural datum.

There is no `length` or `current` unit by design: coordinates are meters (§3.1),
current is normalized away (§3.7), and the one area column carries its unit in its
name.

**Units are fixed by the spec, not carried in the bundle.** The spec admits
exactly one canonical unit per datum (wire/loop → `V/A`, point magnetic → `T/A`),
so a manifest `units:` block would only restate fixed constants: it would carry no
per-bundle information and could be misread as a unit *selector*. The unit of
every quantity is instead pinned by `format.version` plus §3.6, so a bundle stays
self-describing on units (through its version) without a redundant, drift-prone
declaration. The same logic does not apply to coordinate system or sign
convention, which genuinely vary between bundles and so remain declared.

## §3.7 Normalization

Current normalization uses the complex current phasor/Fourier coefficient at
each reported frequency, not peak, RMS, or nominal drive, so multi-frequency and
encoded sources stay comparable.

Turns fold into the normalization precisely *because they are dimensionless*:
`V/A` stays `V/A`. Area cannot, because dividing by m² changes the units. That
asymmetry is why a `point` transmitter must declare `point_moment_area_m2`
(no vertices to supply an area, and the area cannot hide in the normalization),
while finite loops keep their area in their vertices. A `point` receiver needs no
moment column because its datum is already calibrated B-field in `T/A`. The same
dimensionless-turns logic applies on the receive side: a loop receiver's EMF
scales with its turns, so its response is divided by the receiver turn count to a
single-turn loop (area kept in `rx_vertices`).

## §3.8 Missing values

`NaN` is the IEEE 754 token parsed natively by every scientific computing stack.
Output casing varies (`nan` / `NaN` / `NAN`), hence the case-insensitive read. A
fixed token, rather than a configurable sentinel, means a reader never has to
discover what "missing" looks like in a given bundle.

## §3.9 Component naming

The `x`/`y`/`z` letter is opaque because the same letter means different things
across the industry: a contractor may call the inline dipole `Ex`; the MT/EDI
convention takes `Ex` as north; the `easting` axis points east: three directions
behind one letter. csemx records the actual azimuth/vertices, so the data is
unambiguous even though the label is not.

For point magnetic components, `Bx`/`By`/`Bz` naming (never a separate `H*` set)
keeps labels tied to the delivered magnetic-flux-density datum (`T/A`) and avoids
an `A/m` alternative.

## §3.10 Geometry and field type

`wire` geometry denotes electric coupling; `loop` and `point` geometry denote
magnetic coupling. Electric elements are open wire dipoles (grounded or
capacitive); closed loops and compact coils are magnetic. This avoids
electric-loop and magnetic-wire hybrids.

**No stored `*_type` column.** Field type is a total function of geometry
(`wire`→electric, `loop`/`point`→magnetic), and csemx represents electric data as
open-path wire voltages/line integrals over finite baselines, so there is no
electric point. A stored `source_type`/`sensor_type` could therefore only restate
geometry or contradict it (`wire`+`magnetic`), so field type is *derived* from
`geometry_type`, not stored (the "can't be filled in wrong" principle). Geometry,
not field type, also fixes the unit: a `loop` and a `point` are both magnetic but
report `V/A` and `T/A`.

A large transmitter loop is written as its vertices; a small coil (borehole /
crosswell tool, negligible at survey offsets) is a `point` with
`point_moment_area_m2` rather than a polygon of millimeter-scale vertices stacked
on six-figure coordinates. Anchoring on real finite geometry, with one
effective-area escape hatch, lets one model cover surface, borehole, and crosswell
layouts without per-channel length/moment bookkeeping.

## §3.11 Field content: total or secondary

**Secondary is the stored datum; ppm is derived context.** Secondary is defined
by the *primary*: the free-space (no-earth) transmitter response at the receiver,
so secondary = total − primary. The primary must therefore be defined, but it
does not need to be a payload column: csemx needs only one declaration
(`field.content`) because the primary is computed from the geometry the bundle
already carries. ppm is a display/comparison ratio derived outside the csemx
datum, not a stored unit.

**Store the absolute secondary in `V/A`/`T/A`, never literal ppm.** ppm is common
for inductive loop-loop systems (airborne and ground FDEM), but storing it would
break the fixed-unit pillar (§3.6): a dimensionless ×10⁶ ratio is the first datum
whose unit is *not* set by `geometry_type`, the error columns would become ppm,
and a reader assuming `T/A` would mis-scale by ~12 orders. Keeping the datum in
the canonical field unit and recording *which* transform was applied (total vs
secondary) avoids a second unit system or a per-bundle units selector.

**Why secondary is preferred for airborne data.** Total field at the bird is
dominated by the primary; the ground signal is a small ppm-level fraction of it.
Delivering total and asking a consumer to recover the secondary by subtracting
their own computed primary lands every geometry/calibration mismatch on a signal
orders of magnitude smaller. Legacy ppm processing is primary-referenced
precisely to reduce sensitivity to the dominant primary amplitude. Secondary
storage preserves the scattered signal; it is the numerically sound default for
these systems, not merely a convenience.

**Default `total`, so the baseline stays minimal.** Absence of the `field` block
means `total`; total-field bundles need no secondary-specific metadata. Secondary
delivery adds only the `field.content` declaration.

**No primary column: the primary is a derived reference.** Contractor systems may
report ppm internally or in legacy deliverables, but csemx stores the absolute
secondary response, not ppm and not the primary itself. For the free-space
convention used here, the primary is a fixed system response recoverable from the
geometry the bundle already carries. Both sides therefore compute the identical
primary from existing columns; storing it would duplicate a derivable quantity and
break the format's "carry geometry, derive the rest" rule in exactly one place
(§3.7). A stored real primary would also be inadequate for all receiver
datums: the primary is real for a `point` B-field datum but quadrature for a
`loop` EMF datum (§3.5).

**Not airborne-specific.** The same primary-reference machinery covers any
fixed-offset loop-loop FDEM (ground and airborne), so the profile is scoped by
the *measurement* (a removed primary), not by platform.

## §4 Manifest, survey identity, and re-ships

**Survey identity and re-ships.** Re-ship lineage is the tuple
`(contractor, contractor_reference, survey.name)`, ordered by `survey.revision`.
`survey.name` alone can collide across contractors, so the contractor and their
job/contract reference qualify it.

**Per-datum reconciliation over a `survey.part` field.** A survey delivered in
pieces must distinguish "complementary part" from "supersedes," but both look like
multiple bundles with one `survey.name`. csemx uses a single per-datum rule:
highest `survey.revision` wins for repeated datum keys, disjoint data is unioned.
Resolution keys on a *higher* revision, so two copies of one datum key at the same
revision have no tiebreaker and are non-conformant; a corrected datum must
increment the revision. That rule needs no new metadata and is derived from
content plus revision.
`survey.part` would only restate intent the content already carries, and could be
set inconsistently. Lineage comes from survey identity plus `survey.revision`;
hashes, if used, are only for byte-level deduplication.

**Quoted, UTC acquisition dates.** `acquired_start`/`acquired_end` are quoted
strings in one of two exact forms because an unquoted YAML scalar like
`2026-05-01` parses as a date *object*, not a string, and would validate
inconsistently across YAML libraries. UTC with a literal `Z` (no offsets, no local
time) removes timezone ambiguity from a field used only as a day or instant bound.

On ingest, a consumer combining bundles verifies or reprojects coordinate systems
and matches sign conventions (flipping the imaginary part as needed); units need
no reconciliation (fixed by the spec), and IDs are namespaced across bundles to
avoid collision (e.g. `<contractor>:<contractor_reference>:<original_id>`).

## §9 The data table

**One datum per row.** The response at a `frequency` is one physical quantity
regardless of the transmitter drive pattern used to estimate it. `tx_fundamental`
records useful drive provenance when a nominal repetition/fundamental frequency
exists, but does not define datum identity and need not be harmonically related to
`frequency`. Keep the preferred estimate for a datum in one bundle, and ship
competing estimates (alternate stacks, trial processing) as separate bundles.

**All-or-nothing complex datum.** `real`/`imag` are both finite or both `NaN`: a
complex response with only one part present is not a usable measurement, and the
all-or-nothing rule lets a consumer test presence on either part. Errors follow
the datum (finite for a present datum, `NaN` for a missing one) so a skipped
measurement carries no false precision.

**`use` flag.** Some contracts mandate a complete matrix (every frequency ×
station × transmitter), so a contractor cannot *omit* poor data, and inflating
`err` to signal badness corrupts the statistical uncertainty an inversion relies
on; that inflation is irreversible, since a genuinely noisy datum then can't be
told from a producer-deprecated one. `use` separates the producer's quality
judgment from the error: deliver the true value and error, mark `use = 0`.
It is binary and advisory by design: the cutoff for "bad" is subjective, so
the flag is explicitly the producer's include/exclude recommendation, not a
calibrated grade, and the
consumer may override. Kept strictly binary (no levels, no reason codes) to avoid
reimporting the "what does 'fair' mean / where's the cutoff" ambiguity; a reason
goes in `notes.md`. Represented as `0`/`1`, not `true`/`false`, to avoid the
boolean-text casing trap (cf. `exp`, `NaN`).

**Real/imag, not amplitude/phase.** Real/imag is the canonical complex response
and avoids phase wrapping, phase-unit choices, log-amplitude conventions, and a
two-representations-per-bundle switch. Consumers that prefer amplitude/phase can
derive it from the complex value and apply their own error model and floors.

## §11 Versioning

Additive-only minor versions let a `MAJOR.X` reader accept any `MAJOR.Y` bundle
(Y ≤ X) and ignore unknown optional additions, so the format can grow (new
optional columns, manifest keys, files) without breaking existing readers.
Anything that would break a reader bumps `MAJOR`. Because the unit of every
quantity is pinned by `format.version` (§3.6), the version string is also what
keeps a bundle self-describing on units without a manifest units block.

## Out of scope for v1.0

Deliberately deferred:

- **Time-domain (TDEM/TEM).** v1.0 is frequency-domain only and does not define
  gates, waveforms, turn-off ramps, or time-zero conventions.
- **Natural-source EM (MT/AMT).** csemx is controlled-source only; natural-source
  deliverables remain separate.
- **Static/DC data.** `frequency = 0` is not a placeholder for DC resistivity or
  static-limit data; v1.0 data rows require `frequency > 0`.
- **Environmental / medium properties.** Seawater conductivity, CTD profiles,
  borehole fluids, bathymetry, and earth models are modeling inputs, not csemx
  response data.
- **Graded quality codes.** v1.0 keeps only the binary advisory `use` flag.
- **Time-lapse linkage.** Relationships between repeat surveys belong in
  external project metadata.
