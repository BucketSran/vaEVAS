#!/bin/sh
set -eu
exec python3 -B /tests/verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" --tests /tests "$@"
