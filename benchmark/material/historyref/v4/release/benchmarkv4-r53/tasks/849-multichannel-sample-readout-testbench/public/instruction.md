# Multi-channel Sample/Mux/Readout Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Multi-channel Sample/Mux/Readout` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sample_mux_readout_top.va`:
  - Module `sample_mux_readout_top` (entry)
    - position 0: `ch0` (input, electrical)
    - position 1: `ch1` (input, electrical)
    - position 2: `ch2` (input, electrical)
    - position 3: `ch3` (input, electrical)
    - position 4: `clk` (input, electrical)
    - position 5: `rst` (input, electrical)
    - position 6: `sample` (input, electrical)
    - position 7: `read` (input, electrical)
    - position 8: `out` (output, electrical)
    - position 9: `ch_sel_1` (output, electrical)
    - position 10: `ch_sel_0` (output, electrical)
    - position 11: `valid` (output, electrical)
- Artifact `sample_hold_bank.va`:
  - Module `sample_hold_bank` (required_submodule)
    - position 0: `ch0` (input, electrical)
    - position 1: `ch1` (input, electrical)
    - position 2: `ch2` (input, electrical)
    - position 3: `ch3` (input, electrical)
    - position 4: `clk` (input, electrical)
    - position 5: `rst` (input, electrical)
    - position 6: `sample` (input, electrical)
    - position 7: `hold0` (output, electrical)
    - position 8: `hold1` (output, electrical)
    - position 9: `hold2` (output, electrical)
    - position 10: `hold3` (output, electrical)
- Artifact `mux_controller.va`:
  - Module `mux_controller` (required_submodule)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `read` (input, electrical)
    - position 3: `ch_sel_1` (output, electrical)
    - position 4: `ch_sel_0` (output, electrical)
    - position 5: `valid` (output, electrical)
- Artifact `output_driver.va`:
  - Module `output_driver` (required_submodule)
    - position 0: `hold0` (input, electrical)
    - position 1: `hold1` (input, electrical)
    - position 2: `hold2` (input, electrical)
    - position 3: `hold3` (input, electrical)
    - position 4: `clk` (input, electrical)
    - position 5: `rst` (input, electrical)
    - position 6: `read` (input, electrical)
    - position 7: `ch_sel_1` (input, electrical)
    - position 8: `ch_sel_0` (input, electrical)
    - position 9: `out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/sample_mux_readout_top.va`, `./dut/sample_hold_bank.va`, `./dut/mux_controller.va`, `./dut/output_driver.va`
- DUT instance: `XDUT (ch0 ch1 ch2 ch3 clk rst sample read out ch_sel_1 ch_sel_0 valid) sample_mux_readout_top`
- Required saved public traces: `ch0`, `ch1`, `ch2`, `ch3`, `clk`, `rst`, `sample`, `read`, `out`, `ch_sel_1`, `ch_sel_0`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sample_mux_readout_top.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `sample_mux_readout_top.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `sample_mux_readout_top.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `sample_mux_readout_top.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.
- `sample_hold_bank.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `sample_hold_bank.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.
- `mux_controller.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `mux_controller.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `mux_controller.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `mux_controller.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.
- `output_driver.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `output_driver.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_READOUT_RESET_CLEAR`: exercise and make observable: Reset clears held channels, selector, out, and valid. Required traces: `time`, `rst`, `out`, `ch_sel_1`, `ch_sel_0`, `valid`.
- `P_READOUT_SIMULTANEOUS_SAMPLE`: exercise and make observable: An enabled rising clock captures all four input channels into one coherent held bank. Required traces: `time`, `ch0`, `ch1`, `ch2`, `ch3`, `clk`, `rst`, `sample`, `read`, `out`.
- `P_READOUT_CHANNEL_ORDER`: exercise and make observable: Read cycles select held channels in order zero, one, two, three and wrap. Required traces: `time`, `clk`, `rst`, `read`, `ch_sel_1`, `ch_sel_0`.
- `P_READOUT_HELD_VALUE`: exercise and make observable: out equals the held value of the exposed selected channel, independent of later live-input changes. Required traces: `time`, `ch0`, `ch1`, `ch2`, `ch3`, `clk`, `sample`, `read`, `out`, `ch_sel_1`, `ch_sel_0`.
- `P_READOUT_VALID_TIMING`: exercise and make observable: valid is high only for read cycles; when read is low out holds and the pointer does not advance. Required traces: `time`, `clk`, `rst`, `read`, `out`, `ch_sel_1`, `ch_sel_0`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear the held channel values, read pointer, `out`, `ch_sel_1`, `ch_sel_0`, and `valid`.
- When `sample` is high on a rising `clk` edge, `sample_hold_bank` captures `ch0..ch3` simultaneously.
- When `read` is high on a rising `clk` edge, `mux_controller` outputs the next held channel in order 0, 1, 2, 3 and then wraps to 0.
- `output_driver` drives `out` to the selected held channel voltage and asserts `valid` on read cycles.
- `ch_sel_1..ch_sel_0` must expose the channel index currently driven on `out`.
- When `read` is low, hold `out` and deassert `valid` without advancing the pointer.


The required trace names are: `time`, `ch0`, `ch1`, `ch2`, `ch3`, `clk`, `rst`, `sample`, `read`, `out`, `ch_sel_1`, `ch_sel_0`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
