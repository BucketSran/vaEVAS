# Flash Folded DAC4 Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Flash Folded DAC4` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `flash_folded_dac4.va`:
  - Module `flash_folded_dac4` (entry)
    - position 0: `vd4` (input, electrical)
    - position 1: `vd3` (input, electrical)
    - position 2: `vd2` (input, electrical)
    - position 3: `vd1` (input, electrical)
    - position 4: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/flash_folded_dac4.va`
- DUT instance: `XDUT (vd4 vd3 vd2 vd1 vout) flash_folded_dac4`
- Required saved public traces: `vd1`, `vd2`, `vd3`, `vd4`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `flash_folded_dac4.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `flash_folded_dac4.vref` defaults to `1.0`; valid range: finite; overrides vref.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_TREAT_EACH_INPUT_BIT_AS_LOGIC`: exercise and make observable: Treat each input bit as logic one when its voltage is above `vth`. The MSB selects the folded half of the transfer. When `vd4` is high, add the lower-bit weighted value above midscale. When `vd4` is low, subtract the lower-bit weighted value from midscale. The lower bits use binary weights `4`, `2`, and `1`, and the output is scaled by `vref/16`. Required traces: `time`, `vd1`, `vd2`, `vd3`, `vd4`, `vout`.
- `P_VTH_0_45_V_DECISION_THRESHOLD`: exercise and make observable: `vth = 0.45 V`: decision threshold for each voltage-coded input bit. Required traces: `time`, `vd1`, `vd2`, `vd3`, `vd4`, `vout`.
- `P_VREF_1_0_V_OUTPUT_REFERENCE`: exercise and make observable: `vref = 1.0 V`: output reference/full-scale voltage. Required traces: `time`, `vd1`, `vd2`, `vd3`, `vd4`, `vout`.
- `P_VTH_0_45_V_DECISION_THRESHOLD_2`: exercise and make observable: - `vth = 0.45 V`: decision threshold for each voltage-coded input bit. - `vref = 1.0 V`: output reference/full-scale voltage. Required traces: `time`, `vd1`, `vd2`, `vd3`, `vd4`, `vout`.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: exercise and make observable: Use deterministic voltage-domain Verilog-A and voltage contributions only. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels. Required traces: `time`, `vd1`, `vd2`, `vd3`, `vd4`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_TREAT_EACH_INPUT_BIT_AS_LOGIC`: Treat each input bit as logic one when its voltage is above `vth`. The MSB selects the folded half of the transfer. When `vd4` is high, add the lower-bit weighted value above midscale. When `vd4` is low, subtract the lower-bit weighted value from midscale. The lower bits use binary weights `4`, `2`, and `1`, and the output is scaled by `vref/16`.
- `P_VTH_0_45_V_DECISION_THRESHOLD`: `vth = 0.45 V`: decision threshold for each voltage-coded input bit.
- `P_VREF_1_0_V_OUTPUT_REFERENCE`: `vref = 1.0 V`: output reference/full-scale voltage.
- `P_VTH_0_45_V_DECISION_THRESHOLD_2`: - `vth = 0.45 V`: decision threshold for each voltage-coded input bit. - `vref = 1.0 V`: output reference/full-scale voltage.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: Use deterministic voltage-domain Verilog-A and voltage contributions only. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels.


The required trace names are: `time`, `vd1`, `vd2`, `vd3`, `vd4`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
