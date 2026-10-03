# Pipe ADC Gain Control Loop Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Pipe ADC Gain Control Loop` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `pipe_adc_gain_control_loop.va`:
  - Module `pipe_adc_gain_control_loop` (entry)
    - position 0: `din20` (input, electrical)
    - position 1: `din21` (input, electrical)
    - position 2: `din22` (input, electrical)
    - position 3: `din23` (input, electrical)
    - position 4: `din24` (input, electrical)
    - position 5: `din25` (input, electrical)
    - position 6: `din26` (input, electrical)
    - position 7: `clks` (input, electrical)
    - position 8: `dout10` (output, electrical)
    - position 9: `dout11` (output, electrical)
    - position 10: `dout12` (output, electrical)
    - position 11: `dout13` (output, electrical)
    - position 12: `gainctrl0` (output, electrical)
    - position 13: `gainctrl1` (output, electrical)
    - position 14: `gainctrl2` (output, electrical)
    - position 15: `gainctrl3` (output, electrical)
    - position 16: `gainctrl4` (output, electrical)
    - position 17: `gainctrl5` (output, electrical)
    - position 18: `gainctrl6` (output, electrical)
    - position 19: `ddiff` (output, electrical)
    - position 20: `dop` (output, electrical)
    - position 21: `dom` (output, electrical)
    - position 22: `gctrlcode` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/pipe_adc_gain_control_loop.va`
- DUT instance: `XDUT (din20 din21 din22 din23 din24 din25 din26 clks dout10 dout11 dout12 dout13 gainctrl0 gainctrl1 gainctrl2 gainctrl3 gainctrl4 gainctrl5 gainctrl6 ddiff dop dom gctrlcode) pipe_adc_gain_control_loop`
- Required saved public traces: `clks`, `ddiff`, `din20`, `din21`, `din22`, `din23`, `din24`, `din25`, `din26`, `dom`, `dop`, `dout10`, `dout11`, `dout12`, `dout13`, `gainctrl0`, `gainctrl1`, `gainctrl2`, `gainctrl3`, `gainctrl4`, `gainctrl5`, `gainctrl6`, `gctrlcode`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `pipe_adc_gain_control_loop.vlo` defaults to `0.0`; valid range: finite; overrides vlo.
- `pipe_adc_gain_control_loop.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `pipe_adc_gain_control_loop.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `pipe_adc_gain_control_loop.gaincodeinit` defaults to `90`; valid range: finite; overrides gaincodeinit.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_GAIN_CONTROL_INITIAL_STATE`: exercise and make observable: Initialize the gain-control code to `gaincodeinit` and initialize the test-DAC controls to the declared minus phase. Required traces: `time`, `clks`, `ddiff`, `din20`, `din21`, `din22`, `din23`, `din24`, `din25`, `din26`, `dom`, `dop`, `dout10`, `dout11`, `dout12`, `dout13`, `gainctrl0`, `gainctrl1`, `gainctrl2`, `gainctrl3`, `gainctrl4`, `gainctrl5`, `gainctrl6`, `gctrlcode`.
- `P_ALTERNATING_TEST_DAC_PHASES`: exercise and make observable: On rising `clks`, alternate minus and plus test-DAC phases using the sampled 7-bit input code. Required traces: `time`, `clks`, `ddiff`, `din20`, `din21`, `din22`, `din23`, `din24`, `din25`, `din26`, `dom`, `dop`, `dout10`, `dout11`, `dout12`, `dout13`, `gainctrl0`, `gainctrl1`, `gainctrl2`, `gainctrl3`, `gainctrl4`, `gainctrl5`, `gainctrl6`, `gctrlcode`.
- `P_TARGET_DIFFERENCE_GAIN_UPDATE`: exercise and make observable: Update the gain-control code from the plus/minus code difference using the declared target difference and correction polarity. Required traces: `time`, `clks`, `ddiff`, `din20`, `din21`, `din22`, `din23`, `din24`, `din25`, `din26`, `dom`, `dop`, `dout10`, `dout11`, `dout12`, `dout13`, `gainctrl0`, `gainctrl1`, `gainctrl2`, `gainctrl3`, `gainctrl4`, `gainctrl5`, `gainctrl6`, `gctrlcode`.
- `P_GAIN_OUTPUT_LEVELS`: exercise and make observable: Gain-control and test-DAC outputs use valid voltage-coded low/high levels. Required traces: `time`, `clks`, `ddiff`, `din20`, `din21`, `din22`, `din23`, `din24`, `din25`, `din26`, `dom`, `dop`, `dout10`, `dout11`, `dout12`, `dout13`, `gainctrl0`, `gainctrl1`, `gainctrl2`, `gainctrl3`, `gainctrl4`, `gainctrl5`, `gainctrl6`, `gctrlcode`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize the gain-control code to `gaincodeinit`. Initialize the test-DAC controls to the minus phase with `dout13..dout10 = 1000`, initialize the phase so the first sampled backend code is stored as the minus-phase code, and initialize the scalar monitor codes to `dop = 96`, `dom = 32`, and `ddiff = 0` before scaling.

On each rising `clks` crossing, read `din20..din26` as a 7-bit unsigned code. Alternate between minus and plus test-DAC phases: after a minus-phase sample, drive the next plus phase with `dout13..dout10 = 0111`; after a plus-phase sample, return to the minus phase with `dout13..dout10 = 1000`. Store the minus-phase and plus-phase ADC codes, compute the plus-minus code difference, and compare it against a target difference of 64 codes. If the difference is too large, reduce the gain-control code by the absolute error; if too small, increase it by the absolute error. Clamp the gain-control code to `0..127`, emit its bits, and expose the scalar monitor values scaled by `1/100`.


The required trace names are: `time`, `clks`, `ddiff`, `din20`, `din21`, `din22`, `din23`, `din24`, `din25`, `din26`, `dom`, `dop`, `dout10`, `dout11`, `dout12`, `dout13`, `gainctrl0`, `gainctrl1`, `gainctrl2`, `gainctrl3`, `gainctrl4`, `gainctrl5`, `gainctrl6`, `gctrlcode`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
