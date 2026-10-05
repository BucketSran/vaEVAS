# Complete run output

Run a static or transient manifest into a new directory:

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas.results run evas/validation/smoke/idt.json \
  --kernel evas/rust_core/target/debug/evas-kernel --out runs/idt-output
```

`--out` must name a directory that does not exist. Existing files and directories
are never overwritten or deleted. `--timeout` sets the numerical execution
limit in seconds, with the same default as the existing runtime. Kernel identity
has its own five-second query limit. Static mode requires `driven` and `samples`;
transient mode requires `transient`. Missing or mixed modes are rejected.

The output directory contains:

- `input.json`, the original manifest bytes, and `source-N.va`, the exact source
  snapshots compiled for this run. The manifest records original paths, hashes
  and the mapping to snapshot filenames.
- `request.json`, the effective kernel request, including resolved IR and voltage
  tolerances. `result.json` preserves the original decoded machine response.
- `observations.csv`, with `sample_index` for static samples or `time_s` for
  transient observations, followed by ordered `<node>_V` columns. Ground is
  included in the kernel's node order. CSV quoting preserves arbitrary node
  names; finite binary64 numbers round-trip without presentation rounding.
- `manifest.json`, the versioned run record and sole completion marker. It
  records mode, observation count, column units/mapping, file hashes and sizes,
  source/frontend identity, selected package/kernel identity and any failure.

`bundle_version=1` defines this output format. `manifest.json` initially says
`running`. Only a validated response and all required, closed output files permit
the last atomic replacement to `complete`. Validation checks IR and ordered node
identity, exact row counts, finite voltages/diagnostics and requested transient
time coverage. The selected kernel's hash is checked again after execution.
Build revision and request protocol metadata retain the identity interface's
explicit unknown values; the current checkout is not proof of binary origin.

An input/source access failure, compiler rejection, kernel failure, timeout,
incomplete response or write failure returns exit 2 and prints a structured
machine diagnostic on stderr. Failure state is saved as `failed` when writable.
If even failure-state writing fails, stderr reports that extra write error and
the absent or `running` completion marker remains meaningful. Partial snapshots,
responses or CSV files may remain for diagnosis. They are never a complete run
without `manifest.json` saying `complete`. A `manifest.tmp` file is not a marker.
Readers should also verify the recorded hashes before consuming a saved bundle.

This entry adds complete output serialization; existing JSON APIs and CLI actions
remain available. Streaming, SCS save/export, cancellation chunks, packaging and
release installation are outside this interface. Source snapshots may contain
client data; keep their run directories in the owning client/project location
and do not commit raw bulk output.

Implementation is `src/evas/results.py`; public entry and filesystem failure
regressions are `tests/test_result_outputs.py`. Independent static expectations
are -0.75, 0.25 and 1.75 V for `2*u+0.25` at -0.5, 0 and 0.75 V. The transient
case `idt(1,0.25)` expects 0.25, 0.5 and 0.75 V at 0, 0.25 and 0.5 s, checked at
absolute 1e-9 V with reltol 0 and vabstol 1e-9 V. These are local serialization
checks, not simulator qualification or published backend evidence.
