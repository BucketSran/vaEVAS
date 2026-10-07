# Ordered event sources independent contract

This package contains three models with their original tolerances, after
value-preserving decimal-literal normalization, and two separate diagnostics with
1 fs timer tolerance. Each fixture retains the source that failed Spectre lexical
compilation as `original.failedsource.va`. Adding the leading zeros preserves
each binary64 value. Original and normalized EVAS IRs were compared independently
of source locations. EVAS and Spectre use the same normalized source.

The independent formulas use the exact Fraction of each binary64 literal,
written as `Q(value)`. In the mixed model, the PWL root is
`Q(.4)*Q(.3)/(Q(.3)+Q(.1))`. It precedes the periodic timer
`Q(.1)+Q(.2)`, which precedes the one-shot timer `Q(.30000000000000004)`.
The complete event-index sequence is `[0,1,0,2]`. The final `n/k/j` states
are `2/1/1`, and `y=4`.

In the hidden-root model, `z=max(0,t-Q(.1)-Q(.2))`. Its cross root is
`Q(.1)+Q(.2)+Q(1e-18)`, before the one-shot timer. The event-index sequence
is `[0,0,2,1]`. The final `n/q/h/m` states are `2/1/1/1`, and `y=1`.
The tight variant must reject an unrepresentable `1e-20` cross timing tolerance.
A generic execution failure or Spectre segmentation fault does not prove this
specific rejection obligation.

External physical time tolerance is 1 ns. Voltage tolerance is 0.1 µV for the
mixed model and 1 µV for the hidden model. The original hidden EVAS solver
budget remains 1 V with `reltol=0` to isolate event sequencing; the independent
evidence checker applies the tighter physical budget. Coarse and fine manifests
change only observations and maximum step. Each `dut.va` explicitly declares its
timer and cross tolerances. The two 1 fs timer sources are new diagnostics and
do not replace the original configurations.

Run the standalone calibration from this directory:

```sh
python3 -B calibrate.py
```

It checks 21 assertions: 17 acceptance, fault and missing-observation controls,
and four manually expected Fraction states between nearby clocks. The checker
imports no EVAS code. Positive event brackets use exact quarter-nanosecond
fractions. Roundoff can make a nominal binary64 1 ns span exceed the strict
bound, which correctly yields an inconclusive result.

Each fixture contains the actual Spectre deck, include wrapper, EVAS manifests
and reference output plan. Run Spectre on `tb.scs` from the fixture directory.
For a new EVAS execution, compile that fixture's `dut.va` with its manifest
instance mapping. Send the specified sources, stop, maximum step, output times
and solver tolerances to an explicitly identified kernel. Preserve actual
requests, responses and frontend/kernel hashes under a new execution identity.

For a retained observation list containing time and named signal values:

```python
from checker import inspect
result = inspect(rows, family, original_stop)
```

The finite checker skips `y` error within 1 ns of each physical jump and checks
discrete state values outside those windows. That check alone cannot certify the
phase of a query inside the jump window. The separate
[physical-phase checks](candidate-phase/README.md) use independently proven
before/after queries and compare actual states and direct `y` without this
omission.

EVAS event records separately provide event-index order. A tight rejection
requires an adapter that identifies the actual semantic diagnostic and confirms
that there is no accepted waveform. Synthetic rejection calibration does not
substitute for an actual engine result. A shared PSF record does not reveal
exact callback order, and decimal stop projection does not prove exact endpoint
semantics.

[Historical comparison receipts](../../../experiments/backends/ordered-event-sources/README.md)
identify the actual executions. Native raw PSF files, logs and kernel products
remain local-only. These compact receipts do not make historical waveforms
publicly reproducible.
