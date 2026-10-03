# Bugfix EVAS Guide

The writable submission starts as an exact copy of the supplied buggy bundle.
After each meaningful edit, run the exact `command` in
`public/task/evas_runtime.json`. Do not add `--spectre-strict` when that
task-local command omits it.

Use the simulation log and saved traces to test the repair while preserving
the declared file set, interfaces, and unaffected behavior.
