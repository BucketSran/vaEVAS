# Public testbench

`check.py` builds a netlist for each public case, simulates `/app/circuit.va`, reads the output crossings and prints one row per check: case, specification, limit, measured value and PASS/FAIL. The expected crossings are computed from the Spec rules and the stimulus in `contract.py`; no reference waveform is used.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                       # all public cases
python3 /app/testbench/check.py run --case reset_repeat   # one case
```

| Case | What it exercises |
| --- | --- |
| `debruijn` | 4097 words whose absolute codewords (P, F) cover all 64 codewords and all 4096 ordered adjacent pairs; default parameters |
| `reset_repeat` | a repeated word, a reset 20 ps after a capture (the strobe of that word must not appear), a reset while `enc_valid` is high, and a word soon after release |

## Stimulus and measurement

- Inputs switch between 0 V and VIN (1.0 V in the public cases) with 2 ps linear edges centred on the stated times. `sym` changes 300 ps before a capture; `sym_valid` rises 250 ps before it and falls at the capture time.
- `edge_monitor.va` prints every crossing of an output through `vdd`/2 with the time located by the simulator. The checker compares these crossings one to one with the expected ones (S7) and reads the bus values while `enc_valid` is high.
- Crossings before 5 ps are treated as start-up levels, not as edges.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`). `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). Each case has a 1800 s limit.

`run` writes to `--output` (default `/tmp/uwb-encoder-public`): the frozen candidate, one directory per case with the netlist and simulator logs, `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed; an execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
