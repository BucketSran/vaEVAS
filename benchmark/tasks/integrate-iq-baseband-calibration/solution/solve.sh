#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
mkdir -p "/work/."
cp "$source_dir/dut.va" "/work/dut.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/coeff.va" "/work/rtl/coeff.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/inverse.va" "/work/rtl/inverse.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/sample.va" "/work/rtl/sample.va"
