# Airborne frequency-domain EM (HEM) (example)

Synthetic example bundle. A helicopter/fixed-wing frequency-domain EM system: a
moving bird carrying coplanar (`Mcp`/`Bcp`, vertical-axis) and coaxial
(`Mca`/`Bca`, horizontal along-flight) point magnetic dipole pairs at a fixed
~8 m coil separation, flown over three positions along a line (`TXP1`–`TXP3`).

Demonstrates:
- moving point-dipole Tx and Rx (one `tx_station_id` / `rx_station_id` per bird
  position),
- coplanar vs coaxial pairs distinguished purely by `azimuth_deg`/`dip_deg`,
- `altitude.reference: ground` — the bird flies at `altitude = 35` m, with `elev`
  the absolute height; the consumer places it above its own DEM,
- `field.content: secondary` — `real`/`imag` carry the **secondary** (scattered)
  B-field per amp, the free-space primary removed (§3.11),
- independent continuous sinusoidal transmitter frequencies, so `tx_fundamental`
  is omitted,
- a `use = 0` flag on a noisy high-frequency datum.

Secondary field. Airborne FDEM is often reported as **ppm**
(secondary-over-primary), but this bundle keeps the canonical `T/A` unit and
declares `field.content: secondary`, so the stored `real`/`imag` are the
secondary B-field per amp. The free-space primary is computed from the encoded
geometry: for the
~0.196 m² coils (a ~0.5 m-diameter transmitter coil; turns normalized out per
§3.7) at 8 m it is ≈ -3.8e-11 `T/A` coplanar and ≈ +7.7e-11
`T/A` coaxial, so a consumer recovers signed ppm as the datum divided by that
primary (×10⁶). The responses here are order-of-magnitude synthetic HEM values.
All values here are synthetic and not from any real survey.
