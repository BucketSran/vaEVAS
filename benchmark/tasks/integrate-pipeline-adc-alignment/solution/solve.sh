#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
mkdir -p "/work/."
cp "$source_dir/dut.va" "/work/dut.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/coarse.va" "/work/rtl/coarse.va"
mkdir -p "/work/rtl"
cp "$source_dir/rtl/fine.va" "/work/rtl/fine.va"
