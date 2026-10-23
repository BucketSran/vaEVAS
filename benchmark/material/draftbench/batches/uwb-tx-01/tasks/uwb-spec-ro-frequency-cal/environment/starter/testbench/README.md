# Public testbench

`check.py` builds a netlist for each public case, simulates `/app/circuit.va`, reads the recorded crossings and prints one row per check: case, specification, limit, measured value and PASS/FAIL. The expected outputs are computed in `contract.py` from the Spec rules, the stimulus and the observed `ref` and `roclk` crossings: the checker replays the search and counts the RO edges itself. It does not use a reference waveform, and it does not predict counts from the RO tuning law.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                   # all public cases
python3 /app/testbench/check.py run --case ref_lost   # one case
```

| Case | What it exercises |
| --- | --- |
| `normal` | `rst` high until 10 ns, a start at 50 ns and a complete calibration with `n_win` = 16 that ends with `done` |
| `ref_lost` | `n_win` = 24; the reference stops during the fourth window, so the watchdog (S6) ends the calibration with `fail` and the bits kept so far |

## Fixed models and stimulus

- Each calibration instance drives its own RO, `master_ro16.va`: a 16-phase ring oscillator with f = f0 + code × fstep (defaults 600 MHz and 0.25 MHz). Only its phase 0 is connected to `roclk`. It reads a code change 5 ps after the code bits cross 0.5 V and keeps its phase across a frequency change. Its output level is VIN.
- `clock_source.va` generates the 48 MHz reference (period 20.833 ns, 50 % duty, 2 ps edges). Its first rising edge starts at the case's `delay`. With `t_stop` set, no edge starts at or after `t_stop` and the reference stays low, which models a lost reference.
- `cal_start` and `rst` are piecewise-linear sources between 0 V and VIN (1.0 V in the public cases) with 2 ps edges centred on the stated times. Each start is a 2 ns pulse.

## Measurement

- `edge_monitor.va` prints every crossing of `ref` and `roclk` through `vth` and every crossing of an output through `vdd`/2, with the time located by the simulator. The checker compares the output crossings one to one with the expected ones (S10).
- Crossings before 5 ps are treated as start-up levels, not as edges: some simulators ramp every output from 0 V at t = 0.
- `output_probe.va` prints the levels of all outputs once, 5 ns before the first start or reset. An output that starts at its level has no edge, so this reading gives the levels before calibration (S7). Later levels follow from the recorded edges.
- The check "event order is unambiguous" reports the distance from each window edge, start and watchdog reference edge to the nearest RO edge, and the spacing of starts, resets and output changes. The cases are built so that the correct code sequence keeps these distances inside S9.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`). `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). The transient uses maxstep = 100 ps. Each case has a 1800 s limit.

`run` writes to `--output` (default `/tmp/uwb-ro-cal-public`): the frozen candidate, one directory per case with the netlist and simulator logs, `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed; an execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
