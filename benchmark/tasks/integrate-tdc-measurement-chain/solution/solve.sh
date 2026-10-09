#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
mkdir -p "/work/."
cp "$source_dir/dut.va" "/work/dut.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/capture.va" "/work/rtl/capture.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/quantizer.va" "/work/rtl/quantizer.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/formatter.va" "/work/rtl/formatter.va"
