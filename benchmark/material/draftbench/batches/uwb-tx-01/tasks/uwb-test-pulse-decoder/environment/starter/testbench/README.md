# Public testbench

`check.py` builds the netlist of each public case, simulates `/app/circuit.va` together with the fixed transmitter, measures every RF pulse itself, applies the Spec rules S1 to S5 and prints one row per check: case, specification, limit, measured value and PASS/FAIL. The expected symbols, error flags and strobe times come from `contract.py`; no reference decoder is used.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                    # all public cases
python3 /app/testbench/check.py run --case chain288    # one case
```

| Case | What it exercises |
| --- | --- |
| `chain288` | The seed transmitter with its master RO at code 288 (672 MHz, δ = 93.0 ps) sends 120 known symbols: all 64 symbols once in random order, then 56 random ones. The decoder sees `outp`/`outn` on `vp`/`vn` and the RO tap `ph0` on `clk`. `rst` is high until 1 ns, and one more decoder reset falls between two pulses near symbol 70; the transmitter is not reset there, so the next symbol is decoded from P_prev = 0 and differs from the one sent. Default parameters. |

## The transmitter (fixed public models)

`chain/` holds the seed transmitter of the IR-UWB circuit family: 6-bit serial-to-symbol converter, DPPM + FSK encoder, 16-phase master RO, pulse generator, branch scheduler, eight RF branch oscillators, two envelope lanes, and the combiner with the differential output. The bench drives it as the family's chain test does: an ideal 4.032 GHz bit clock at six times the RO rate, the RO code held by ideal sources, and the transmitter reset released before the first bit. Each symbol leaves as one pulse in the second frame after the encoder takes it. Each pulse is a raised-cosine envelope 9δ long on carrier f_F, so its start and centre lie a few picoseconds after the grid points because of the envelope response. You may read these models; do not edit them.

## Measurement

- The run saves `outp` and `outn`. The checker forms v = outp − outn, finds the crossings of |v| through `v_det` and the zero crossings by linear interpolation between the simulator's time points, and groups exceedances into pulses with `t_gap` (S1). It repeats this at `v_det` ± 1 mV: a carrier peak that close to `v_det` can move t_f or t_l by half a carrier period, and then the expectation is a range (S9).
- `edge_monitor.va` prints every crossing of `sym[5:0]`, `sym_valid` and `err` through `vdd`/2 and every rising crossing of `clk` through 0.5 V. The checker takes δ from the mean clk period and the frame edges from these crossings (S2).
- For each pulse the checker computes P, e, f, F, D, the symbol and the error flag. It compares them with the decoder's outputs in the middle of the matching `sym_valid` pulse, and compares the `sym_valid` crossings with t_l + `t_lat` + `tr`/2 and t_l + `t_lat` + `t_pw` + `tr`/2. `measured.json` in each case directory lists the measured P, F, symbol, flag, position error (ps) and relative frequency error of every pulse.
- The run stops after the strobe of the last sent symbol. The transmitter then keeps sending words of all zeros or all ones until the stop time. Pulses whose strobe would start after the stop time are not graded.
- Crossings before 5 ps are treated as start-up levels, not as edges.
- If a case leaves the operating domain of S8, the run reports an execution problem and does not judge the model.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`). `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). The transient uses `maxstep` = 10 ps. Each case has a 1800 s limit; the public case takes about 15 s on EVAS 0.8.7.

`run` writes to `--output` (default `/tmp/uwb-decoder-public`): the frozen candidate, one directory per case with the netlist, the simulator logs, the saved waveform and `measured.json`, then `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed or left the operating domain; an execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
