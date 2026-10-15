# SAR Logic 4b Self Timed Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SAR Logic 4b Self Timed` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sar_logic_4b_self_timed.va`:
  - Module `sar_logic_4b_self_timed` (entry)
    - position 0: `vdd` (input, electrical)
    - position 1: `gnd` (input, electrical)
    - position 2: `clkc` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `dcmpp` (input, electrical)
    - position 5: `dcmpn` (input, electrical)
    - position 6: `cmpck` (output, electrical)
    - position 7: `dout1` (output, electrical)
    - position 8: `dout2` (output, electrical)
    - position 9: `dout3` (output, electrical)
    - position 10: `dout4` (output, electrical)
    - position 11: `dbotp1` (output, electrical)
    - position 12: `dbotp2` (output, electrical)
    - position 13: `dbotp3` (output, electrical)
    - position 14: `dbotn1` (output, electrical)
    - position 15: `dbotn2` (output, electrical)
    - position 16: `dbotn3` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sar_logic_4b_self_timed.va`
- DUT instance: `XDUT (vdd gnd clkc rst dcmpp dcmpn cmpck dout1 dout2 dout3 dout4 dbotp1 dbotp2 dbotp3 dbotn1 dbotn2 dbotn3) sar_logic_4b_self_timed`
- Required saved public traces: `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sar_logic_4b_self_timed.t_logic_delay` defaults to `100p`; valid range: finite; overrides t_logic_delay.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_INITIALIZES_SELF_TIMED_STATE`: exercise and make observable: Initialization and rising `rst` reset the conversion step, clear `cmpck/dout`, and initialize DAC bottom-plate controls. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.
- `P_COMPARATOR_PULSE_DECISION_POLARITY`: exercise and make observable: Rising `dcmpp` or `dcmpn` pulses store comparator decisions with the declared polarity. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.
- `P_STEP_ADVANCE_ON_COMPARATOR_FALL`: exercise and make observable: Comparator-output falling events advance the SAR step and update the next control state. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.
- `P_CMPCK_TIMING_AND_LEVEL`: exercise and make observable: `cmpck` is scheduled low after `t_logic_delay` and driven with valid voltage-coded levels. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

At initialization and on each rising `rst` transition, reset the conversion to step 4, clear `cmpck` and `dout1..dout4`, and initialize `dbotp1..dbotp3` and `dbotn1..dbotn3` high. A rising `clkc` transition schedules `cmpck` high after `t_logic_delay`.

Each rising comparator pulse on `dcmpp` or `dcmpn` schedules `cmpck` low after `t_logic_delay`. At the pulse, treat `dcmpp > dcmpn` as a positive decision and store that decision in `dout{step}` for the current MSB-to-LSB step sequence 4, 3, 2, 1. For steps above 1, a positive decision clears the positive bottom-plate control `dbotp{step-1}`, while a negative decision clears the negative bottom-plate control `dbotn{step-1}`. Step 1 only latches `dout1` and does not update a bottom-plate control. When the comparator pulse falls, decrement the step and re-enable `cmpck` after `t_logic_delay` while further decisions remain.


The required trace names are: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
