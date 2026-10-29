# Public testbench

Run from `/app`:

```sh
python3 /app/testbench/check.py --output /app/output/public-check
```

This runs `dynamics-0`. `--case NAME` selects one of these public cases. The
candidate defaults to `/app/circuit.va`; `--candidate PATH` supports local
experiments, with declared helper files beside that file. The immutable public
`cases.json` contains the stimuli, saved signals and observation configuration.
The `Spec` in the instruction defines the behavior and acceptance conditions.
This implementation-stage diagnostic has not received current author calibration.

The backend is Spectre. A trusted deployment must provide its licensed executable
and libraries; set `SPECTRE` to the executable path if it is not on `PATH`. The
Python-only development image cannot perform a transient without that deployment.
The checker uses a new working directory per case and copies candidate bytes
unchanged to its legacy `dut.va` name. Helper names do not change. Fixed support
assets are loaded from the published case record, including checked file hashes
where present. The netlists in the case record are complete inputs to this runner.
Standalone `.scs` files are retained as inspectable development examples.

Each call creates an `attempt-*` directory in the requested output directory. It
retains submission hashes, the backend version if available, raw checker output,
case logs and waveforms when produced. `boundary.json` describes the latest
attempt. Exit code 0 means all public observations passed, 1 means a valid public
circuit verdict failed, and 2 means no complete valid verdict was obtained.
Public feedback is diagnostic and is not the final task score. A missing backend
does not establish that the model is semantically wrong.

Final evaluation uses a verifier image built from `tests/Dockerfile`. That image
contains the fixed checks but no starter candidate. Only collected artifacts
are restored to `/app`; a missing artifact therefore stays missing. The trusted
Spectre deployment must be available in both environments. Final evaluation
uses the same public behavioral contract and fixed numerical evaluator with its
own cases. The Harbor boundary writes score 0 for a failed executed attempt and
keeps the original checker report, including a null checker reward on execution
errors. Such a zero does not validate a negative calibration example.
