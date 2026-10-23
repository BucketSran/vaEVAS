# Public testbench

`check.py` builds a netlist for each public case, simulates `/app/circuit.va`, reads the output crossings and prints one row per check: case, specification, limit, measured value and PASS/FAIL. The expected crossings come from a replay of the Spec rules on the lane stimulus in `contract.py`; no reference waveform is used. The last row of each case lists the scheduler paths that the case exercises (for example `cold`, `warm_tail`, `take_over`, `drop`, `hold_waiting`, `idle_hold_off`); it is informational and always passes.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                   # all public cases
python3 /app/testbench/check.py run --case conflict   # one case
```

| Case | What it exercises |
| --- | --- |
| `hold` | `n_pre` = 2, 16 symbols, default parameters. Same-branch pairs with positions 7 → 0 (the windows touch: hand-over without TAIL), 6 → 0 (request while the branch is ACTIVE, window starts in TAIL), 4 → 0 (request in TAIL, the branch holds until the window) and 3 → 0, 2 → 0 (the idle HOLD ends before the request: OFF, then a cold start), separated by other branches. `rst` is high until 0.3 ns. |
| `conflict` | `n_pre` = 15, 12 symbols. Three different branches with positions 7, x, 0 in a row: the third request finds two busy branches and is dropped, once on lane b and once on lane a. |

## Lane stimulus

The lanes are not produced by a pulse-generator model in the netlist. `contract.windows` computes them from a list of frames on an ideal `delta0` grid. Frame i starts at t0 + 16·i·`delta0`, with t0 = 0.5 ns. A frame holds a descriptor (P, F) or is empty. The descriptor of frame i is scheduled into frame i + 1:

- its window starts at t0 + (16·(i + 1) + P)·`delta0` and lasts 9·`delta0`;
- its request (`pre_x` rising) comes `n_pre`·`delta0` before the window start, and `pre_x` falls when `rf_x` rises;
- `sel_x` = F changes `delta0`/2 after frame i starts;
- scheduled descriptors alternate between lane a and lane b, and empty frames do not take a lane.

Every input edge is linear, 2 ps long, and centred on its stated time. The public cases use VIN = 1.0 V.

## Measurement

- `edge_monitor.va` prints every crossing of an output through a threshold, using the crossing time located by the simulator. `pwr`, `pre`, `rel`, `gate_a`, `gate_b` and `conflict` are monitored at `vdd`/2, `st[k]` at 0.1, 0.3, 0.5, 0.7, 0.9 and 1.1 V, and `nsup` at 0.5, 0.9, 1.1, 1.5, 1.9 and 2.1 V (0.1 V on either side of every level).
- Rows are grouped per output: one row per branch for `pwr`, `pre` and `rel`, one row per branch for `st`, and one row each for `gate_a`, `gate_b`, `conflict` and `nsup`. The limit column gives the expected number of crossings and how many of them are timed (S10).
- "At most two branches powered" counts the observed `pwr` crossings, independent of the replay.
- Crossings before 5 ps are treated as start-up levels, not as edges.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`). `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). The transient analysis uses `maxstep` = 10 ps. Each case has a 1800 s limit.

`run` writes to `--output` (default `/tmp/uwb-scheduler-public`): the frozen candidate, one directory per case with the netlist and simulator logs, `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed; an execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
