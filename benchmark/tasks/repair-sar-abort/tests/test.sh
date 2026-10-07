#!/bin/sh
set -eu
python3 /tests/verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}"
