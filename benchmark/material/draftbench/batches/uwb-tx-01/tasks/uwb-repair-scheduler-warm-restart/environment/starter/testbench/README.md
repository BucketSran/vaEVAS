# Public testbench

`check.py` freezes a copy of `/app/modules`, builds the fixed transmit-chain netlist for each public case, simulates it, reads the recorded crossings and the saved output, and prints one row per check: case, specification, limit, measured value and PASS/FAIL. The expected crossings and the expected RF output are computed from the Spec rules and the stimulus in `contract.py`; no reference waveform is used.

```sh
python3 /app/testbench/check.py plan
python3 /app/testbench/check.py run                   # all public cases
python3 /app/testbench/check.py run --case hold       # one case
python3 /app/testbench/check.py run --output /tmp/my-run
```

| Case | What it exercises |
| --- | --- |
| `hold` | 16 words. Same-carrier pairs with positions 7 -> 0 (touching pulses), 6 -> 0 and 4 -> 0 (the carrier must run on), and 3 -> 0 and 2 -> 0 (the branch turns off and restarts cold), separated by other carriers. Polarity bits and DPC gains are not all equal. Default `n_pre`, `t_tail` and `t_hold`. |
| `conflict` | 12 words with `n_pre` = 15. Requests for a third carrier find both supplies busy, so two symbols are dropped, one on each lane. Three same-carrier requests are warm grants on supply slot 1. |

`plan` also prints how many requests of each kind the Spec rules give for each case (warm grants, warm grants from an idle HOLD, cold grants, preemptions, drops). The first row of each case in `run` repeats this as a check of the case design.

## Bench wiring

The netlist includes every `.va` file of the frozen module directory, then `clock_source.va` and `edge_monitor.va`. It connects the modules by port order exactly as below. Bus nodes are listed most significant bit first, so `pwr7 ... pwr0` connects to `pwr[7:0]`.

```text
Vc9 ... Vc0   (c9 ... c0)  dc sources for the RO code 288
Xbclk (bclk) uwb_clock_source period=Tb delay=t_d tr=2p
Vrst, Vdin, Vpol           piecewise-linear sources (C1); Ven (en 0) vsource dc=1
Xs2p (bclk din rst sym5 sym4 sym3 sym2 sym1 sym0 sym_valid) uwb_serial_to_symbol6
Xenc (sym5..sym0 sym_valid rst p2 p1 p0 i2 i1 i0 f2 f1 f0 q7..q0 enc_valid) uwb_dppm_fsk_encoder8
Xro  (c9..c0 ph15..ph0) uwb_master_ro16
Xpg  (ph15..ph0 p2 p1 p0 f2 f1 f0 pol enc_valid en rst pre_a rf_a sa2 sa1 sa0 pol_a
      pre_b rf_b sb2 sb1 sb0 pol_b overrun) uwb_pulse_generator n_pre=N
Xsch (pre_a rf_a sa2 sa1 sa0 pre_b rf_b sb2 sb1 sb0 rst pwr7..pwr0 pre7..pre0 rel7..rel0
      gate_a gate_b conflict nsup st7..st0) uwb_ro_scheduler8 n_pre=N [t_tail=...] [t_hold=...]
Xbr0 ... Xbr7 (pwrk prek relk vrok) uwb_rf_ro_branch f_rf=f_k
Xenva (gate_a ph0 env_a) uwb_envelope_lane
Xenvb (gate_b ph0 env_b) uwb_envelope_lane
Xout (vro7..vro0 env_a env_b gate_a gate_b sa2 sa1 sa0 sb2 sb1 sb0 pol_a pol_b outp outn)
     uwb_tx_output [dpc_db0=...] ...
```

`clk672` in the Spec is the node `ph0`. The exact netlist of each case is written to `<output>/<case>/tb.scs`.

## Stimulus and measurement

- The bit clock, `rst`, `din` and `pol` follow Spec C1. Their edges are 2 ps long and centred on the stated times.
- `edge_monitor.va` instances on `ph0`, `pwr0`...`pwr7`, `pre0`...`pre7`, `rel0`...`rel7`, `gate_a`, `gate_b` and `conflict` (threshold 0.5 V) and on `nsup` (thresholds 0.5, 1.5 and 2.5 V) print every crossing with the time the simulator locates. The checker compares these crossings one to one with the expected ones (C9) and ignores the last 5 ps of each run.
- Crossings before 5 ps are treated as start-up levels, not as edges. The simulator ramps every `transition()` output from 0 V at t = 0.
- `outp` and `outn` are saved at every accepted simulator step. The reconstruction (C9) is evaluated at those points.

## Simulator and outputs

The declared backend is the EVAS voltage-domain simulator (`python3 -m evas simulate`). `EVAS_PYTHONPATH`, `EVAS_KERNEL` and `EVAS_PYTHON` can point at a specific installation. `UWB_BACKEND=legacy` selects EVAS 0.8.7 instead (`LEGACY_EVAS_SRC`, `LEGACY_EVAS_PY`). The netlist uses `maxstep=10p`. Each case has a 1800 s limit.

`run` writes to `--output` (default `/tmp/uwb-chain-public`): the frozen module copy in `candidate/`, one directory per case with the netlist and simulator logs, `timing.json`, `results.json` and `results.md`. Exit status 0 means every public check passed, 1 means a check failed, and 2 means a case could not be executed. An execution problem is not a verdict on the model. Public results are diagnostics and do not give the task score.
