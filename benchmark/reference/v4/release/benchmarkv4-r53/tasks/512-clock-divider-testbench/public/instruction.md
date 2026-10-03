# Clock Divider Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clock Divider` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `clk_divider_ref.va`:
  - Module `clk_divider_ref` (entry)
    - position 0: `clk_in` (input, electrical)
    - position 1: `rst_n` (input, electrical)
    - position 2: `div_code_0` (input, electrical)
    - position 3: `div_code_1` (input, electrical)
    - position 4: `div_code_2` (input, electrical)
    - position 5: `div_code_3` (input, electrical)
    - position 6: `div_code_4` (input, electrical)
    - position 7: `div_code_5` (input, electrical)
    - position 8: `div_code_6` (input, electrical)
    - position 9: `div_code_7` (input, electrical)
    - position 10: `clk_out` (output, electrical)
    - position 11: `lock` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/clk_divider_ref.va`
- DUT instance: `XDUT (clk_in rst_n div_code_0 div_code_1 div_code_2 div_code_3 div_code_4 div_code_5 div_code_6 div_code_7 clk_out lock) clk_divider_ref`
- Required saved public traces: `clk_in`, `rst_n`, `div_code_0`, `div_code_1`, `div_code_2`, `div_code_3`, `div_code_4`, `div_code_5`, `div_code_6`, `div_code_7`, `clk_out`, `lock`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `clk_divider_ref.vdd` defaults to `0.9` V; valid range: vdd > 0; sets output high levels.
- `clk_divider_ref.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets clock, reset, and code thresholds.
- `clk_divider_ref.trf` defaults to `1e-11` s; valid range: trf > 0; sets output rise and fall smoothing.
- `clk_divider_ref.td` defaults to `0.0` s; valid range: td >= 0; sets output transition delay.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET`: exercise and make observable: Active-low reset clears divider phase and drives clk_out and lock low. Required traces: `time`, `clk_in`, `rst_n`, `clk_out`, `lock`.
- `P_RATIO_DECODE`: exercise and make observable: The LSB-first 8-bit code selects the divide ratio, with code zero mapped to ratio one. Required traces: `time`, `clk_in`, `div_code_0`, `div_code_1`, `div_code_2`, `div_code_3`, `div_code_4`, `div_code_5`, `div_code_6`, `div_code_7`, `clk_out`.
- `P_DIVIDED_PERIOD`: exercise and make observable: For ratios above one, successive clk_out rising edges span the decoded number of clk_in rising edges. Required traces: `time`, `clk_in`, `clk_out`.
- `P_ODD_RATIO_DUTY`: exercise and make observable: Odd ratios retain both phases with floor/ceil segment lengths differing by at most one input cycle. Required traces: `time`, `clk_in`, `clk_out`.
- `P_LOCK_REACQUIRE`: exercise and make observable: lock asserts after one complete output period and clears/reacquires when the ratio changes. Required traces: `time`, `clk_in`, `rst_n`, `div_code_0`, `div_code_1`, `div_code_2`, `div_code_3`, `div_code_4`, `div_code_5`, `div_code_6`, `div_code_7`, `clk_out`, `lock`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT is a resettable, voltage-domain PLL/ADPLL feedback divider with an 8-bit programmable ratio code and a lock indicator.

- Treat all inputs and outputs as electrical voltage-domain signals.
- Interpret `rst_n` as active-low reset. While reset is low, clear the divider
  state and drive `clk_out` and `lock` low.
- Decode `div_code_0` through `div_code_7` as an unsigned 8-bit LSB-first
  voltage-coded ratio. Code 0 maps to divide ratio 1.
- For divide ratio 1, reproduce the input clock activity on `clk_out` and
  assert `lock` after the first valid post-reset clock cycle.
- For divide ratios greater than 1, generate a periodic divided clock whose
  rising-to-rising output period spans the decoded number of input rising
  edges after startup.
- For odd divide ratios, use floor/ceil segment lengths so both high and low
  phases are present and the long segment differs by at most one input cycle
  from the short segment.
- Assert `lock` only after the first complete output period for the current
  decoded ratio. If the ratio code changes after reset, clear divider phase and
  `lock`, then reacquire using the new ratio.


The required trace names are: `time`, `clk_in`, `rst_n`, `div_code_0`, `div_code_1`, `div_code_2`, `div_code_3`, `div_code_4`, `div_code_5`, `div_code_6`, `div_code_7`, `clk_out`, `lock`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
