#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
mkdir -p "/work/."
cp "$source_dir/dut.va" "/work/dut.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/detector.va" "/work/rtl/detector.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/gain.va" "/work/rtl/gain.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/amplifier.va" "/work/rtl/amplifier.va"
