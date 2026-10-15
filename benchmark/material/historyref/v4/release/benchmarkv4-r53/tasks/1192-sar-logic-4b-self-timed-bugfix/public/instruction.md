# SAR Logic 4b Self Timed Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

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

## Public Parameter Contract

- `sar_logic_4b_self_timed.t_logic_delay` defaults to `100p`; valid range: finite; overrides t_logic_delay.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RESET_INITIALIZES_SELF_TIMED_STATE`: restore: Initialization and rising `rst` reset the conversion step, clear `cmpck/dout`, and initialize DAC bottom-plate controls. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.
- `P_COMPARATOR_PULSE_DECISION_POLARITY`: restore: Rising `dcmpp` or `dcmpn` pulses store comparator decisions with the declared polarity. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.
- `P_STEP_ADVANCE_ON_COMPARATOR_FALL`: restore: Comparator-output falling events advance the SAR step and update the next control state. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.
- `P_CMPCK_TIMING_AND_LEVEL`: restore: `cmpck` is scheduled low after `t_logic_delay` and driven with valid voltage-coded levels. Required traces: `time`, `clkc`, `cmpck`, `dbotn1`, `dbotn2`, `dbotn3`, `dbotp1`, `dbotp2`, `dbotp3`, `dcmpn`, `dcmpp`, `dout1`, `dout2`, `dout3`, `dout4`, `rst`, `vdd`, `gnd`.


The following canonical public behavior is normative for this derived form:

At initialization and on each rising `rst` transition, reset the conversion to step 4, clear `cmpck` and `dout1..dout4`, and initialize `dbotp1..dbotp3` and `dbotn1..dbotn3` high. A rising `clkc` transition schedules `cmpck` high after `t_logic_delay`.

Each rising comparator pulse on `dcmpp` or `dcmpn` schedules `cmpck` low after `t_logic_delay`. At the pulse, treat `dcmpp > dcmpn` as a positive decision and store that decision in `dout{step}` for the current MSB-to-LSB step sequence 4, 3, 2, 1. For steps above 1, a positive decision clears the positive bottom-plate control `dbotp{step-1}`, while a negative decision clears the negative bottom-plate control `dbotn{step-1}`. Step 1 only latches `dout1` and does not update a bottom-plate control. When the comparator pulse falls, decrement the step and re-enable `cmpck` after `t_logic_delay` while further decisions remain.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `sar_logic_4b_self_timed.va`.
Every supplied `.va` file is editable; do not add or omit files.
