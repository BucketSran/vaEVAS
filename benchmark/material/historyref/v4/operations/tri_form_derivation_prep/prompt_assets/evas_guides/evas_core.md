# Direct EVAS Guide

Use the installed `evas` executable directly. The public task mount contains
the complete visible test and `evas_runtime.json`. Keep only final candidate
artifacts in the writable submission mount; use `/tmp/vabench-visible/` for
generated simulator output and per-case work directories.

Run the exact command declared by the task-local `evas_runtime.json`. Most
tasks use `--spectre-strict`; tasks whose public contract requires `$rdist_*`
use portable EVAS mode because cross-simulator PRNG sequence identity is not
certified. Inspect the log and generated `tran.csv` waveforms when testing a
hypothesis. EVAS does not return a private
score, checker decision, gold comparison, or hidden diagnostic. The final
trusted replay uses the same test bytes and fixtures exposed here.

Do not edit the read-only task mount. Do not look for evaluator source, gold,
hidden parameters, or a feedback broker; none is part of the public runtime.
