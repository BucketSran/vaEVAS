#!/bin/sh
set -eu
exec python3 /tests/verify.py --candidate /app/circuit.va --output /logs/verifier
