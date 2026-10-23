# Public testbench

`check.py` builds a netlist for each public case, simulates `/app/circuit.va`, reads the saved `vro` waveforms and prints one row per check: case, specification, limit, measured value and PASS/FAIL. The expected waveform is computed from the Spec rules and the stimulus in `contract.py`; no reference waveform is used.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                      # all public cases
python3 /app/testbench/check.py run --case cold_starts   # one case
```

| Case | What it exercises |
| --- | --- |
| `cold_starts` | Two instances on the same inputs: `seed` with default parameters and `ideal` with `t99_amp` = `t99_freq` = 0 and `df_start` = 0. Two cold starts at VIN = 1.0 V. First: `pwr` and `pre` rise at 1.0 ns, `pre` falls and `rel` rises at 1.186 ns, `pwr` and `rel` fall together at 3.5 ns. Second: `pwr` and `pre` rise at 5.0 ns, `pre` falls and `rel` rises at 5.186 ns, `rel` falls at 6.5 ns, `pwr` falls at 7.0 ns. |

## Stimulus and measurement

- Inputs are piecewise-linear sources with 2 ps linear edges centred on the stated times. The release and stop times used for the expected waveform are the `vth` crossings of these ramps, computed per instance from its `vth`.
- The transient analysis uses `maxstep=1p`; the simulator may add points. The checker reads `vro` of every instance from the saved waveform file (`tran.csv`).
- Rows per instance:
  - `vro saved and finite`: every saved point is a finite number.
  - `vro = 0 while off, precharging or stopped`: the largest |`vro`| outside the released intervals.
  - `vro follows S2`: the largest |`vro` − S2| inside the released intervals.
  - Both value rows skip saved points within 3 ps of a `pwr` or `rel` crossing.
  - `release N ... zero crossings`: zero crossings of `vro` by linear interpolation between saved points, compared one to one with the times where the S2 phase equals π/2 + kπ. The window runs from 5 ps after the release to 5 ps before the stop; an end that lies within 1 ps of an expected crossing moves 2 ps inward. The value also shows the first and last full cycle (from three consecutive zero crossings) next to the S2 values, so the start-up frequency offset and its decay are visible.
  - `cold starts repeat`: the zero crossings of each release, measured from its release time, against those of the first release.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`). `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). Each case has a 1800 s limit.

`run` writes to `--output` (default `/tmp/uwb-rf-branch-public`): the frozen candidate, one directory per case with the netlist, simulator logs and saved waveforms, `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed; an execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
