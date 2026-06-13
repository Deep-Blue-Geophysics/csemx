#!/usr/bin/env sh
set -eu

PYTHON="${PYTHON:-python3}"
FULL=0

case "${1:-}" in
  --full)
    FULL=1
    shift
    ;;
  --help|-h)
    echo "usage: tools/check_examples.sh [--full]" >&2
    exit 0
    ;;
esac

if [ "$#" -ne 0 ]; then
  echo "usage: tools/check_examples.sh [--full]" >&2
  exit 2
fi

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: Python interpreter not found: $PYTHON" >&2
  exit 2
fi

has_pyarrow() {
  "$PYTHON" -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("pyarrow") else 1)' >/dev/null 2>&1
}

validate_bundle() {
  if [ "$FULL" -eq 1 ]; then
    "$PYTHON" tools/validate_csemx.py --full "$1"
  else
    "$PYTHON" tools/validate_csemx.py "$1"
  fi
}

for bundle in examples/*.csemx; do
  case "$bundle" in
    *example_mixed_parquet.csemx)
      if [ "$FULL" -eq 1 ] || has_pyarrow; then
        validate_bundle "$bundle"
      else
        echo "SKIP: $bundle (pyarrow not installed for $PYTHON)"
      fi
      ;;
    *)
      validate_bundle "$bundle"
      ;;
  esac
done

validate_bundle examples/example.csemx.zip
