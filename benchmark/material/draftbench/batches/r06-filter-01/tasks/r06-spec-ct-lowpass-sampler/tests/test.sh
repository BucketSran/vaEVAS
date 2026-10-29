#!/bin/sh
set -eu
TESTS=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
exec python3 -B "$TESTS/harbor_entry.py" --candidate "${CANDIDATE:-/app/circuit.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}"
