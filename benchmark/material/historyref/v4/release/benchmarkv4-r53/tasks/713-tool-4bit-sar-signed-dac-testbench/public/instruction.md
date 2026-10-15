# Tool 4bit SAR Signed DAC Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Tool 4bit SAR Signed DAC` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `tool_4bit_sar_signed_dac.va`:
  - Module `tool_4bit_sar_signed_dac` (entry)
    - position 0: `d0` (input, electrical)
    - position 1: `d1` (input, electrical)
    - position 2: `d2` (input, electrical)
    - position 3: `d3` (input, electrical)
    - position 4: `sh` (input, electrical)
    - position 5: `aout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/tool_4bit_sar_signed_dac.va`
- DUT instance: `XDUT (d0 d1 d2 d3 sh aout) tool_4bit_sar_signed_dac`
- Required saved public traces: `aout`, `d0`, `d1`, `d2`, `d3`, `sh`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `tool_4bit_sar_signed_dac.vth` defaults to `0.9`; valid range: finite; overrides vth.
- `tool_4bit_sar_signed_dac.gain` defaults to `1.8 / 16.0`; valid range: finite; overrides gain.
- `tool_4bit_sar_signed_dac.tr` defaults to `1p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_EACH_RISING_CROSSING_OF_SH`: exercise and make observable: On each rising crossing of `sh` through `vth`, evaluate bits `d3..d0` with weights `8, 4, 2, 1`. A high bit contributes the positive weight and a low bit contributes the negative weight. Drive `aout` to the signed weighted sum multiplied by `gain` and hold it until the next sample trigger. Required traces: `time`, `aout`, `d0`, `d1`, `d2`, `d3`, `sh`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising crossing of `sh` through `vth`, evaluate bits `d3..d0` with weights `8, 4, 2, 1`. A high bit contributes the positive weight and a low bit contributes the negative weight. Drive `aout` to the signed weighted sum multiplied by `gain` and hold it until the next sample trigger.


The required trace names are: `time`, `aout`, `d0`, `d1`, `d2`, `d3`, `sh`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
