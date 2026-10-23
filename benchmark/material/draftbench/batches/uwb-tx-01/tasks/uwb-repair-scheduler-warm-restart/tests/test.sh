#!/bin/sh
set -eu
exec python3 /tests/verify.py --candidate /app/modules --output /logs/verifier
