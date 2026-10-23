# Public testbench

`check.py` builds a netlist for each public case, simulates `/app/circuit.va` with the fixed oscillator `master_ro16.va`, reads the output crossings and prints one row per check: case, specification, limit, measured value and PASS/FAIL. `contract.py` computes the expected crossings from the Spec rules, the stimulus and the tap edges observed in the same run. No reference waveform is used.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                        # all public cases
python3 /app/testbench/check.py run --case late_enable     # one case
```

| Case | What it exercises |
| --- | --- |
| `positions` | 14 descriptors, one per frame from frame 2, latched at different phases of the frame. The sequence covers every P, 7 → 0 and 0 → 7, and the same F on consecutive windows that touch (the RF window on one lane ends at the tap edge where the window on the other lane starts). Default parameters, `en` always high. |
| `late_enable` | `en` low until the middle of frame 6. The words of frames 2 to 5 overwrite each other (overrun), and the word of frame 5 is scheduled at the frame-7 edge. Then come an overrun with `en` high, an empty frame, a word latched just after the frame edge that took its predecessor, and touching windows with the same F. |

## Stimulus and measurement

- Oscillator: `master_ro16` (f = 600 MHz + code × 0.25 MHz) with its code bits from dc sources. Both public cases use code 288 (672 MHz, δ = 93.006 ps) and phase0 = 0, so the first frame edge is at 1.488 ns. Only the observed tap crossings are used for expected values; the code and the phase only place the stimulus.
- The inputs switch between 0 V and VIN (1.0 V in the public cases) with 2 ps linear edges centred on the stated times. `rst` is high from the start until the middle of a tap interval before the first frame edge.
- Each descriptor is placed at a stated fraction of its frame. `pos`, `fcode` and `pol` change 25 ps before the `enc_valid` rise and hold until the next descriptor. `enc_valid` stays high for 400 ps, or for less when the next descriptor follows within 550 ps.
- `edge_monitor.va` prints every crossing of each tap through the instance's `vth`, and of each output through `vdd`/2, with the time located by the simulator. The checker numbers the tap edges, replays S3 to S7 on them and compares the output crossings one to one (S9). It also reads `sel_x`, `pol_x` and `rf_x` one `tr` after each window start.
- Each run lasts until every scheduled window has ended. Crossings before 5 ps are treated as start-up levels, not as edges.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`). `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). The transient analysis uses `maxstep=10p`. Each case has a 1800 s limit.

`run` writes to `--output` (default `/tmp/uwb-pg-public`): the frozen candidate, one directory per case with the netlist and simulator logs, `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed; an execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
