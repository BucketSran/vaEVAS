#!/bin/sh
set -eu
python /tests/verify.py --candidate /work/output/dut.va --output /logs/verifier/results --tests /tests
