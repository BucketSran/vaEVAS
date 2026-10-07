#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" "$@"
