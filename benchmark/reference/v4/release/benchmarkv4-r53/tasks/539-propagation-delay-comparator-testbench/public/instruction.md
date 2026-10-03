# Propagation Delay Comparator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Propagation Delay Comparator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cmp_delay.va`:
  - Module `cmp_delay` (entry)
    - position 0: `CLK` (input, electrical)
    - position 1: `VINN` (input, electrical)
    - position 2: `VINP` (input, electrical)
    - position 3: `DCMPN` (output, electrical)
    - position 4: `DCMPP` (output, electrical)
    - position 5: `LP` (output, electrical)
    - position 6: `LM` (output, electrical)
    - position 7: `VSS` (inout, electrical)
    - position 8: `VDD` (inout, electrical)
- Artifact `edge_interval_timer.va`:
  - Module `edge_interval_timer` (entry)
    - position 0: `CLK_1` (input, electrical)
    - position 1: `CLK_2` (input, electrical)
    - position 2: `OUT_PS` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/cmp_delay.va`, `./dut/edge_interval_timer.va`
- DUT instance: `IDUT (clk vinn vinp out_n out_p lp_int lm_int gnd vdd) cmp_delay`
- DUT instance: `IEIT (clk out_p delay_ps) edge_interval_timer VTH=0.45`
- Required saved public traces: `clk`, `vinn`, `vinp`, `out_n`, `out_p`, `lp_int`, `lm_int`, `gnd`, `vdd`, `delay_ps`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cmp_delay.voffset` defaults to `0.0` V; valid range: finite real; subtracts an input-referred offset from VINP minus VINN.
- `cmp_delay.tau` defaults to `4.34e-12` s; valid range: tau > 0; sets the logarithmic regeneration-delay sensitivity.
- `cmp_delay.td_0` defaults to `2.05e-11` s; valid range: td_0 >= 0; sets the base clock-to-decision delay.
- `cmp_delay.td_min` defaults to `2e-11` s; valid range: 0 <= td_min <= td_max; sets the minimum scheduled decision delay.
- `cmp_delay.td_max` defaults to `2e-10` s; valid range: td_max >= td_min; sets the maximum scheduled decision delay.
- `edge_interval_timer.VTH` defaults to `0.4` V; valid range: VTH > 0; sets the rising-edge threshold for both timer inputs.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CLOCKED_DECISION`: exercise and make observable: At each rising CLK crossing through half the VDD-to-VSS rail span, the comparator latches the sign of VINP minus VINN minus voffset into complementary DCMPP/DCMPN decisions, with LP mirroring DCMPP and LM mirroring DCMPN. Required traces: `time`, `clk`, `vinn`, `vinp`, `gnd`, `vdd`, `out_n`, `out_p`, `lp_int`, `lm_int`.
- `P_FALLING_RESET`: exercise and make observable: Each falling CLK crossing resets both comparator decision outputs low. Required traces: `time`, `clk`, `out_n`, `out_p`.
- `P_DELAY_MAGNITUDE_TREND`: exercise and make observable: For otherwise equal conditions, a smaller absolute effective differential input produces a longer clock-to-decision delay. Required traces: `time`, `clk`, `vinn`, `vinp`, `out_p`, `out_n`.
- `P_DELAY_CLAMP`: exercise and make observable: The scheduled comparator decision delay follows the public log-linear regeneration relation and remains within td_min through td_max. Required traces: `time`, `clk`, `vinn`, `vinp`, `vdd`, `out_p`, `out_n`.
- `P_EDGE_INTERVAL_MEASUREMENT`: exercise and make observable: After a rising CLK_1 crossing arms the timer, the next rising CLK_2 crossing updates OUT_PS to the elapsed interval expressed in picoseconds and holds that completed measurement. Required traces: `time`, `clk`, `out_p`, `delay_ps`.
- `P_BUNDLE_BINDING`: exercise and make observable: The timing helper observes the comparator clock as CLK_1 and the positive comparator decision as CLK_2, exposing their measured interval on delay_ps. Required traces: `time`, `clk`, `out_p`, `delay_ps`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the comparator decision outputs low.
- Use `V(VDD,VSS)/2` as the comparator clock threshold.
- On each rising clock crossing, latch the sign of
  `V(VINP,VSS) - V(VINN,VSS) - voffset`.
- Schedule the decision outputs using a log-linear regeneration delay:
  compute `vdiff_eff = abs(V(VINP,VSS) - V(VINN,VSS) - voffset)`, floor it at
  a small positive value to avoid `ln(0)`, compute
  `td_raw = td_0 + tau * ln(V(VDD,VSS) / vdiff_eff)`, and clamp the result to
  `[td_min, td_max]`.
- On each falling clock crossing, reset the comparator decision outputs low.
- Drive `LP` with the same delayed voltage-coded state as `DCMPP` and `LM`
  with the same delayed voltage-coded state as `DCMPN`.
- Drive the timing helper so it captures the time between rising crossings of
  `CLK_1` and `CLK_2`, converts that interval to picoseconds, and holds the
  most recent completed measurement on `OUT_PS`.


The required trace names are: `time`, `clk`, `vinn`, `vinp`, `out_n`, `out_p`, `lp_int`, `lm_int`, `gnd`, `vdd`, `delay_ps`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
