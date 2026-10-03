# Testbench EVAS Guide

The read-only task mount exposes a reference DUT and five mutation fixtures.
Their exact paths and direct command template are in `evas_runtime.json`.

To test the candidate, use the command template to copy `testbench.scs` into a
per-case directory under `/tmp/vabench-visible/`, bind that directory's `dut`
path to one listed read-only fixture, and invoke `evas simulate` on the copied
candidate. Repeat for the reference and all five mutations. The final replay
uses these same six fixtures. Do not put run directories, waveform output, or
fixture links under `public/submission/`.
