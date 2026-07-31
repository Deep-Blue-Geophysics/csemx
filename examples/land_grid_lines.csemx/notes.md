# Land CSEM — intersecting grid lines and `groups.csv` (example)

Synthetic example bundle. Two intersecting land survey lines — an E–W receiver
line `L200E` (stations `R01`–`R05` at northing 3626000) and a N–S line `L300N`
(stations `R11`, `R03`, `R12`, `R13` at easting 552500) — crossing at station
`R03`. Two fixed grounded electric bipole transmitters: `TX1` (400 m, E–W) west
of `L200E`, and `TX2` (200 m, N–S) at the south end of `L300N`.

This bundle exists to demonstrate the optional `groups.csv` element-membership
table (spec §10):

- **Intersecting lines and many-to-many membership** — the crossing station
  `R03` belongs to *both* lines through two membership rows, one per
  `(group_kind, group_id)`.
- **`sequence` values are ranks, not indices** — sequences are unique within
  `(group_kind, group_id, element_kind)` and need not be contiguous: `L200E`
  ranks its receivers `0, 10, 20, 30, 40` (tens reserved for possible infill
  stations), while `L300N` uses `0–3`.
- **Fixed Tx shooting an Rx line** — `TX1` shoots the receivers of `L200E` but
  is deliberately *not* a member of that line (it sits off its west end and is a
  source, not a traverse station); its data rows connect to the line only
  through the receivers. No group membership is needed to model its data.
- **One line holding both TX and RX members with independent sequences** —
  `L300N` contains `TX2` (tx sequence `0`) and four receivers (rx sequences
  `0–3`); tx and rx orderings are independent, so sequence `0` appears once per
  `element_kind`.
- **Component-level membership** — the `array` kind group `MAGZ` collects the
  two vertical magnetic point coils by populating `component_id`
  (`R03/Bz`, `R12/Bz`), while all line memberships are station-wide (blank
  `component_id`, covering every component at the station).

Group membership is element metadata only: it assigns no group to any data row
and changes no datum's meaning (§10). A consumer might use it to select data by
receiver line, or purely for plotting.

Station `R03` carries a fuller sensor set (`Ex`, `Ey`, `Bz`) than the plain
inline stations, as a crossing station often does; `Ex`/`Ey` labels are opaque
join keys — orientation always comes from the vertices (§3.9).

All values are synthetic and not from any real survey.
