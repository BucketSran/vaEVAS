# Public testbench

Run from `/app`:

```sh
python3 /app/testbench/check.py --output /app/output/public-check
```

This runs `contract-base`, the only public case. `--case NAME` selects a case
from the public `cases.json`. The candidate defaults to `/app/circuit.va`;
`--candidate PATH` supports local experiments. The immutable public `cases.json`
contains the stimulus netlist, saved signals, parameter values and observation
grid. `visible_test.scs` is the same netlist with the include path set to
`/app/circuit.va`, kept as an inspectable development example. The `Spec` in
the instruction defines the behavior and acceptance conditions. This
implementation-stage diagnostic has not received author calibration.

## What the public case exercises

`contract-base` uses the default parameters, fixed supplies `VDD = 0.9 V` and
`VSS = 0 V`, 20 ps clock edges and a 12 ns run. `vin` moves before the first
trigger, changes inside and after aperture windows, ramps through one aperture
instant, and keeps moving during long holds. One clock pulse is shorter than
`taperture`, and one trigger follows the previous trigger by 260 ps. It is a
representative case, not the complete final coverage.

## Observation method

The netlist saves `vdd`, `vss`, `clk`, `vin` and `vout` with
`strobeperiod=2p`. The checker reads only these saved samples. Trigger times
are the rising crossings of `vth` by `clk`, located by linear interpolation
between adjacent samples; the aperture instants are those times plus
`taperture`. The accepted held range of a capture is the minimum and maximum
of the linearly interpolated `vin` trace over the aperture instant +/- 2 ps.
The hold and transition windows and their tolerances are exactly those in the
Spec. A sample spacing above 2.1 ps, a missing signal, or a stimulus outside
the contract is reported as an evidence or checker error, not as a model
failure.

## Backend, outputs and exit codes

The backend is Spectre. A trusted deployment must provide its licensed executable
and libraries; set `SPECTRE` to the executable path if it is not on `PATH`. The
Python-only development image cannot perform a transient without that deployment.
Each case runs in a new working directory with a 120 s limit. The checker copies
candidate bytes unchanged to its legacy `dut.va` name.

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
uses the same public behavioral contract and the same checker with its own
cases. The Harbor boundary writes score 0 for a failed executed attempt and
keeps the original checker report, including a null checker reward on execution
errors. Such a zero does not validate a negative calibration example.
