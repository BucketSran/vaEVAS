# Ordered event history comparison

Four original configurations with 1 ns timer tolerance failed the independent 1 µV voltage/sample contract in Spectre. Two separate diagnostics use 1 fs timer tolerance and stricter numerical settings. Their finite voltage and callback checks pass: maximum z error is 0.15472284 µV for the linear model and 0.06849270 µV for the nonlinear model. EVAS replay covers all 595 and 4,086 numeric in-domain points from those references. These passes do not replace the four original failures.

Explicit saves expose the strict models' n, m, h and s variables. Final counts are 3/2/0, all five callbacks satisfy the unchanged 1 ns physical timing budget, and no cross fires. The original `allwithnodes` configuration did not expose counters; those event checks remain inconclusive. Every exact scientific endpoint remains inconclusive. The third n update and second m update share one exported record, so their counts do not prove the order of the two extremely close callbacks.

[summary.json](summary.json) retains all six results. [receipt.json](receipt.json) identifies sources, decks, checker, frontend, kernel, actual settings and archived outputs. [Original triage](original-history-triage.json) separates stored-sample plateau error from differences across a discontinuity. [Callback audit](strict-callback-audit.json) records the strict configuration's actual changes and exact-domain limits. [Frozen inputs and checker](../../../evas/validation/ordered_event_history/README.md) support new executions.

The derived settings reader recognizes ms, pV, fA and aA. Its positive and dimension-rejection controls are retained. It reads actual log/PSF settings without substituting requested values and does not qualify waveform export origin.

Original raw archives, request/response data and historical binaries remain local-only under `current/runs/event-closure-20261008/`. Checksums identify that evidence; they are not public download links. These development results do not establish general Spectre compatibility or a paper pass count.

Each EVAS manifest names `dut.va` by relative path. It does not embed source contents, so a fine-grid manifest can have the same hash as a strict-timer manifest. Use both source and manifest hashes from the receipt to identify an experiment.
