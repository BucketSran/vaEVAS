# Public Runtime Contract

The task-local `public/task/evas_runtime.json` is the only authority for public EVAS execution. Read it on every task instead of assuming a command from memory.

## DUT and Bug-Fix Tasks

The contract names `public/submission` as the candidate root and binds a fixed
visible deck. Run its exact `command`; most tasks use:

```text
evas simulate public/task/visible_test.scs -o /tmp/vabench-visible/evas-output --spectre-strict
```

Tasks whose declared behavior requires `$rdist_*` instead publish the same
command without `--spectre-strict` and declare `compatibility_mode: portable`.
Do not add the flag back. For these tasks, EVAS evidence establishes the
checker-facing functional and statistical properties inside the public loop;
it does not claim pointwise identity with Spectre's pseudorandom sequence.

Do not pass a case. Do not edit `visible_test.scs`. In a native tool runtime, call `run_evas` with no arguments; the runner resolves the pinned executable and fixed deck.

## Testbench Tasks

The candidate is `public/submission/testbench.scs`. The contract provides exactly six public fixture bindings:

- `reference`
- `mutation_01`
- `mutation_02`
- `mutation_03`
- `mutation_04`
- `mutation_05`

Use the exact `candidate_command_template` and the matching `dut_root` supplied
for each case. As with DUT tasks, do not add `--spectre-strict` when the
task-local template omits it. The candidate must include its DUT below `./dut`;
absolute paths and parent-directory escapes are outside the public contract.

Run one case at a time when diagnosing, then all six after the final edit. With a native `run_evas` tool, pass the selected public case name. With bash, substitute only fields already present in the JSON contract.

## Public Outputs

In the bash runtime, output is placed below `/tmp/vabench-visible/evas-output` (or its task-local sandbox mapping). Useful public evidence may include:

- process return code and standard output/error;
- simulator logs;
- `tran.csv` and its saved columns;
- optional strobe or display output.

An optional file is not required unless the task or runtime contract says so. A zero return code means the declared public simulation completed; it does not run the private checker.

In the native tool runtime, the tool result may contain only bounded stdout/stderr diagnostics. Do not assume filesystem access to a trace that the tool did not return.

## Security Boundary

The public runtime intentionally excludes evaluator assets, gold source, private cases, private mutation identities, and final score decisions. Any attempt to infer or locate them invalidates the workflow. The final evaluator may exercise stricter or broader behavior than the visible run.
