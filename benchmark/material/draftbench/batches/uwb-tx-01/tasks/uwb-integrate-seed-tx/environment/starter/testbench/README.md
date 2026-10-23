# Public testbench

`check.py` freezes `/app/circuit.va` together with a fresh copy of `/app/modules/`, checks the Deliverable rules on the frozen file, builds a netlist for each public case, simulates it, and prints one row per check: case, specification, limit, measured value and PASS/FAIL. The expected behavior is computed in `contract.py` from the Spec rules, the stimulus and the observed `clk672` crossings; no reference waveform is used.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                    # all public cases, about 1 to 2 minutes
python3 /app/testbench/check.py run --case decode      # one case
```

| Case | What it exercises |
| --- | --- |
| `decode` | `n_win = 2`; calibration, then 48 random words sent after `done`; `pol` low; default `n_pre`, gain, common mode and carriers |
| `early_conflict` | `n_win = 1`, `n_pre = 15`, `pol` high; data starts 12 frames before `done` (only the word pending at the first enabled frame is sent), then position sequences 7, x, 0 on three carriers that leave no free supply, so three words are dropped with a `conflict` pulse |

## Stimulus

- Each case instantiates the transmitter once: `Xtx (bclk din rst ref cal pol outp outn done fail conflict nsup clk672) uwb_tx_seed <parameters>`.
- `ref`: ideal 48 MHz square wave from `clock_source.va` (2 ps edges, first rising edge at the case's reference delay). `rst` is high from 0 to 10 ns. `cal_start` rises at 40 ns (a 2 ns pulse). `pol` is a constant level per case.
- `bclk` and `din` come from `bit_source.va`, an ideal ×6 multiplier of `clk672` (the CDC test condition, S6). From the first rising `clk672` crossing at or after the case's start time, each frame of length T (the last measured `clk672` period) carries six `bclk` pulses that rise (j + 0.25)·T/6 and fall (j + 0.75)·T/6 after the frame edge, j = 0..5. `din` changes at the falling `bclk` edges, so word n occupies data frame n. After the last word the source sends three zero bits, which make the encoder take the last word, then stops.
- All stimulus edges are 2 ps linear ramps; a crossing is at the ramp midpoint.

## Measurement

- The simulator saves `outp`, `outn`, `nsup`, `clk672`, `bclk`, `done`, `fail` and `conflict`. Threshold crossings are taken from the saved waveforms by linear interpolation between time points (0.5 V for logic pins; 0.5 V and 1.5 V for `nsup`). Crossings before 5 ps are start-up, not edges.
- Pulses in `outp − outn` are the groups of samples with |v| > 0.2 × g_pa, where samples less than 180 ps apart belong to one group; each pulse extends to the midpoints of the gaps to its neighbours. Its start is the energy centroid ∫t·v² dt / ∫v² dt minus T_w/2 minus 10.9 ps. P is the nearest tap of the `clk672` frame that contains the start; D comes from the spacing to the previous pulse; F is the nearest carrier to the frequency from the zero crossings in the middle half of the window.
- The correlation for S4 is ∫v·m dt / sqrt(∫v² dt ∫m² dt) over the window, where m is the expected envelope times the branch carrier (phase from the branch's release time given by the S5 replay), multiplied by (−1)^pol.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`), with `maxstep = 10 ps`. `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). Each case has a 1800 s limit.

`run` writes to `--output` (default `/tmp/uwb-integrate-public`; use an absolute path): the frozen candidate and library, one directory per case with the netlist, simulator log and saved waveforms, `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed; an execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
