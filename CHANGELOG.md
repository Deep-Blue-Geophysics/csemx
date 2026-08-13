# Changelog

Notable changes to the csemx format and its reference tooling. Release tags
are `vX.Y.Z`, where `X.Y` is the format version the release defines and `Z`
is the tooling patch level (see [RELEASING.md](RELEASING.md)).

## 0.2.0 (unreleased)

Format 0.2 (beta minor; per spec §12 readers accept only the exact format
version they implement, so 0.1 bundles must be re-exported as 0.2):

- A present datum may now carry `NaN` in both `err_real` and `err_imag`,
  meaning the producer delivered no uncertainty estimates (common for
  contractor processing chains that do not report them). Errors are pairwise
  all-or-nothing: one finite and one `NaN` is invalid, and a missing datum
  still requires `NaN` errors. Consumers that need uncertainties apply their
  own error model or floors. For present DC data, `err_imag = 0` is required
  only when errors are delivered.
- The bundle's top-level directory name must now start with a letter, digit,
  or underscore (excluding `.`, `..`, hidden directories, and option-like
  `-`-prefixed names) and must not end with a dot (stripped by Windows). The
  charset is unchanged.

## 0.1.0 (2026-08-13)

First public release of csemx: a beta of the format specification, the
`csemx` Python package (reader, writer, validator, CLI), MATLAB helpers,
seven example bundles, a fill-in template bundle, and a plain-language
quickstart. During the 0.x beta, format minor versions may include breaking
changes and readers accept only the exact format version they implement
(spec §12).

The v0.1 data model incorporates the changes adopted in the July 2026
community review of the draft. No reviewer identified a defect in the core
data model; all changes were additions or scoping decisions:

- Optional `groups` table for transmitter/receiver element membership in
  named lines, arrays, and other producer-defined collections (#1), with an
  intersecting-grid example bundle (#2).
- Optional navigation/attitude columns and sub-second `time_utc` on `tx` and
  `rx` for moving platforms — advisory QA/QC metadata that never alters
  modeling geometry (#3).
- `frequency = 0` for DC and static-limit data (DC resistivity, MMR), with
  DC conventions for normalization, polarity, and field content (#4).
- Time-domain roadmap statement; the time-domain data model itself is
  deferred post-v1.0 (#5).
- Accessibility package: plain-language quickstart with spreadsheet warning
  and glossary (#6), editable template bundle (#7), and a non-normative
  reading guide in the specification (#8).

With thanks to the July 2026 reviewers: E. Attias (UTIG), S. Constable
(Scripps), S. MacInnes (Zonge), A. Haroon (U. Hawaii), J. Barrett
(Southernrock, via Anglo American), T. Ritchie (GRS), and D. Werthmüller
(ETH, forwarded).
