# Seafloor CSEM — vector node + deep-towed HED (example)

Synthetic example bundle. A 300 m horizontal electric dipole transmitter
deep-towed ~50 m above the seafloor, recorded at three tow positions
(`TX001`–`TX003`, decreasing offset) by one seafloor receiver node `SF01` with a
full vector sensor set: horizontal electric dipoles `Ex`/`Ey` (10 m), a vertical
electric dipole `Ez` (3 m), and three point magnetic coils `Bx`/`By`/`Bz`.

Demonstrates:
- a moving transmitter (one `tx_station_id` per tow position),
- `altitude.reference: seafloor` — the node sits on the seafloor (`altitude = 0`)
  and the towed source flies at `altitude = 50` m, with `elev` carrying the
  absolute (negative) height,
- a vertical electric dipole (`Ez`, vertices differing in `elev`/`altitude`),
- `tx_fundamental` for transmitter-drive provenance and a `use = 0` flag on the
  noisy far-offset vertical-dipole datum (`TX001 → Ez`).

All values are synthetic and not from any real survey.
