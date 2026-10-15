# DUT EVAS Guide

Write the declared DUT artifacts under `public/submission/`, then run the exact
`command` in `public/task/evas_runtime.json`. Do not add
`--spectre-strict` when that task-local command omits it.

The visible deck includes the current submission by relative path. Use the
simulation log and saved public traces to check interface, event, level,
timing, and metric behavior before finalizing the candidate.
