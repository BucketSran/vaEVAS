# Public checks and native execution

The public checker and author final checker use the same analytical contract and native measurement code. The protocol is still awaiting decisions on its public domain and accuracy target. Current commands do not launch a simulator unless you explicitly choose `run`; pending protocol fields also block that action before any process launch. The runtime code has only been tested with software process doubles. No rebuilt-task VA or container execution has been performed.

## Inspect and prepare

From `/app`, use:

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py render --output /tmp/r01-benches
python3 /app/testbench/check.py prepare --candidate /app/circuit.va --output /tmp/r01-prepare
```

`plan` prints the public PWL stimuli and analytical observations. `render` writes native Spectre netlists, a node mapping and expected observations. `prepare` validates the finalized public protocol, freezes the candidate and builds a fresh complete attempt without launching any process. While domain/accuracy decisions remain pending, prepare reports `not_run` with the missing decision and no score. Reusing an attempt directory is rejected rather than mixing new and old files.

The exploratory plan defaults to a 1 ns grid and 10 ps event guard. These numbers remain proposals until the Spec's measurement budget is finalized. The plan includes startup, stop, interval/input-segment midpoints and both sides of strict control crossings. Startup is never removed. A guard that removes a whole required mode interval or the stop observation is rejected. Event exclusions never move the reference sampling instant away from window close.

| Public experiment | Diagnostics |
| --- | --- |
| `startup` | All initial modes and separate track/reset equality controls that cannot mask each other's comparison |
| `windows` | Continuous ramp tracking, close-time sampling, input changes during hold and reopening |
| `reset_history` | Previous sample erasure, priority, close during reset and both release modes |
| `isolation` | Nondefault parameters and independently driven simultaneous instances |

The reference is calculated from PWL input values and the current reset/tracking/holding interval. It never reads gold output. Example fixture values do not finalize the permitted numerical domain.

## Execute only when authorized

A trusted deployment must provide licensed Spectre on PATH or set `SPECTRE` to its executable path, with the license environment initialized before running Python. The Python image does not contain commercial binaries. The selected target version is `21.1.0.509.isr12`, a version already present in repository evidence; this round has not queried an installed simulator. A mismatch fails preflight and retains the execution cause. Each case has a 120 s timeout including the launch, with a 30 s license wait. The version probe has a 30 s timeout. These are author run settings pending actual execution qualification.

The following command is a real simulation request and was not executed during authoring:

```sh
python3 /app/testbench/check.py run --candidate /app/circuit.va --output /tmp/r01-public-run
```

The runner copies one stable regular `circuit.va`, records its SHA-256, restores author-owned stimuli, requests native `strobetimes`, and reads scalar PSF ASCII values. It selects native records within the declared timestamp tolerance; it does not interpolate across a switch or accept model-printed values. Missing/incomplete/nonfinite data and changed frozen inputs fail with explicit reasons. Native node values also verify the applied input and controls. The process group is terminated after timeout, including children surviving the leader.

Outputs include frozen source, requested protocol/cases/plan, per-case netlists, version and process logs, native waveforms, observed points and diagnostics. Public execution produces diagnostic results and no task reward. These results are not final scoring inputs.

The final checker uses a separate trusted baseline, copies only the declared VA submission, reruns all public representatives plus the author extensions, and writes a task-level 0/1 result and `reward.txt` for an executed attempt. Unexecuted preparation has null score and no reward. Actual environment setup, simulator acceptance and numerical calibration remain unverified; software process-double scores are marked `software-test-double` and never recorded as real VA evidence.

The static submission preflight checks standard includes and obvious external file/process operations, including simple local object macros. It is not a complete VA preprocessor or an OS sandbox. The separate trusted deployment must enforce its execution isolation; the runner does not install a local simulator or provision credentials.

## Diagnose an existing trace

Offline CSV columns are `case,instance,probe,time,vin,track,rst,vout`, using seconds and volts. Each planned key must appear once. Missing, duplicate, extra, nonfinite, shifted-time, incorrect-stimulus and wrong-output observations are reported with the expected value, actual value, time, mode and limit.

```sh
python3 /app/testbench/check.py check --csv /tmp/observed.csv --voltage-atol "$DIAGNOSTIC_VOLTAGE_ATOL" --time-atol "$DIAGNOSTIC_TIME_ATOL"
```

Explicit offline tolerances are diagnostic choices, not changes to final acceptance. Exit 0 means pass or successful planning/rendering, 1 means diagnostic failure, and 2 means invalid input, pending protocol or preparation without an executed result. Solver-written benches may supplement development feedback. They do not supply final results.
