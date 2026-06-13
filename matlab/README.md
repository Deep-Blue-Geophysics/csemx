# csemx — MATLAB helpers

Reader, writer, and a validation wrapper for [csemx](../README.md) bundles,
packaged under the `+csemx` namespace. Paths below are relative to the
repository root.

## Contents

- `+csemx/read.m` — `csemx.read(path)` → a struct (manifest and notes as text,
  the five tables as MATLAB tables)
- `+csemx/write.m` — `csemx.write(bundle, path)` (a directory, or a `.zip` when
  `path` ends in `.zip`)
- `+csemx/validate.m` — `csemx.validate(path)` (runs the Python validator)
- `+csemx/private/` — internal helpers, not called directly

## Setup

Add the `matlab/` directory (the parent of `+csemx/`) to the MATLAB path:

```matlab
addpath("matlab");      % from the repository root
```

Requires MATLAB R2019b or later (the functions use `arguments` blocks).
`csemx.validate` additionally needs a Python 3 interpreter with the csemx
validator available (see [`../python`](../python)); select a specific
interpreter with the `Python` name-value argument.

## Usage

```matlab
bundle = csemx.read("examples/example.csemx");   % struct: .manifest, .tx, .rx, .data, ...
csemx.write(bundle, "out.csemx.zip");            % pass Overwrite=true to replace
[ok, output] = csemx.validate("examples/example.csemx", Full=true);
```
