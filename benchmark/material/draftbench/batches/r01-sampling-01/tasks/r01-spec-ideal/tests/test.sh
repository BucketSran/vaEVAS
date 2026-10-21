#!/bin/sh
set -eu
# Invoking the verifier is an explicit simulator execution request.
exec python3 /tests/verify.py --candidate /app/circuit.va --output /logs/verifier --execute
