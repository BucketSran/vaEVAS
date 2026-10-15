# vaBench Agentic Submission Contract

Inspect the mounted public task inputs and write only the final candidate
artifacts under `public/submission/`. Preserve exact file names, module names,
ports, parameters, and required artifact paths.

The public task mount contains a transparent EVAS runtime package. Invoke
`evas` directly against its visible test and keep generated output under
`/tmp/vabench-visible/`. Do not emit evaluator, score, debug-only, simulator
output, fixture links, or self-reported PASS/FAIL files as candidate artifacts.

The visible closed loop runs on EVAS. The `--spectre-strict` option enables
EVAS's stricter compatibility mode; it does not invoke Cadence Spectre or
guarantee identical results from Spectre. EVAS and Spectre can differ in
adaptive time-step placement, observation around `timer`, `cross`, and
`transition`, handling of `$bound_step`, and diagnostics for invalid models.
Implement the public behavioral contract with portable Verilog-A semantics.
Do not rely on a solver's raw output-row density, exact adaptive sample times,
or permissive handling of invalid constructs. A visible EVAS pass establishes
the outcome of this public EVAS loop only.
