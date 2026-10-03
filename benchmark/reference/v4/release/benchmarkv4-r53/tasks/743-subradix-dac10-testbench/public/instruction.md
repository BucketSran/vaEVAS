# Subradix DAC10 Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Subradix DAC10` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `subradix_dac10.va`:
  - Module `subradix_dac10` (entry)
    - position 0: `vd9` (input, electrical)
    - position 1: `vd8` (input, electrical)
    - position 2: `vd7` (input, electrical)
    - position 3: `vd6` (input, electrical)
    - position 4: `vd5` (input, electrical)
    - position 5: `vd4` (input, electrical)
    - position 6: `vd3` (input, electrical)
    - position 7: `vd2` (input, electrical)
    - position 8: `vd1` (input, electrical)
    - position 9: `vd0` (input, electrical)
    - position 10: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/subradix_dac10.va`
- DUT instance: `XDUT (vd9 vd8 vd7 vd6 vd5 vd4 vd3 vd2 vd1 vd0 vout) subradix_dac10`
- Required saved public traces: `vd0`, `vd1`, `vd2`, `vd3`, `vd4`, `vd5`, `vd6`, `vd7`, `vd8`, `vd9`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `subradix_dac10.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `subradix_dac10.vref` defaults to `1.0`; valid range: finite; overrides vref.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_TREAT_EACH_INPUT_AS_LOGIC_ONE`: exercise and make observable: Treat each input as logic one when its voltage is greater than `vth`. Decode `vd9..vd0` as a sub-radix word whose adjacent bit weights follow radix `1.8`, with `vd0` weight one and `vd9` weight `1.8^9`. Scale the active-weight sum by the all-ones sub-radix weight sum so that all ones maps to `vref`. Required traces: `time`, `vd0`, `vd1`, `vd2`, `vd3`, `vd4`, `vd5`, `vd6`, `vd7`, `vd8`, `vd9`, `vout`.
- `P_VTH_0_45_V_DECISION_THRESHOLD`: exercise and make observable: `vth = 0.45 V`: decision threshold for each input bit. Required traces: `time`, `vd0`, `vd1`, `vd2`, `vd3`, `vd4`, `vd5`, `vd6`, `vd7`, `vd8`, `vd9`, `vout`.
- `P_VREF_1_0_V_OUTPUT_FULL`: exercise and make observable: `vref = 1.0 V`: output full-scale/reference voltage. Required traces: `time`, `vd0`, `vd1`, `vd2`, `vd3`, `vd4`, `vd5`, `vd6`, `vd7`, `vd8`, `vd9`, `vout`.
- `P_VTH_0_45_V_DECISION_THRESHOLD_2`: exercise and make observable: - `vth = 0.45 V`: decision threshold for each input bit. - `vref = 1.0 V`: output full-scale/reference voltage. Required traces: `time`, `vd0`, `vd1`, `vd2`, `vd3`, `vd4`, `vd5`, `vd6`, `vd7`, `vd8`, `vd9`, `vout`.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: exercise and make observable: Use deterministic voltage-domain Verilog-A and voltage contributions only. It is acceptable to express sub-radix weights with portable real arithmetic such as `pow(1.8, k)`. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels. Required traces: `time`, `vd0`, `vd1`, `vd2`, `vd3`, `vd4`, `vd5`, `vd6`, `vd7`, `vd8`, `vd9`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_TREAT_EACH_INPUT_AS_LOGIC_ONE`: Treat each input as logic one when its voltage is greater than `vth`. Decode `vd9..vd0` as a sub-radix word whose adjacent bit weights follow radix `1.8`, with `vd0` weight one and `vd9` weight `1.8^9`. Scale the active-weight sum by the all-ones sub-radix weight sum so that all ones maps to `vref`.
- `P_VTH_0_45_V_DECISION_THRESHOLD`: `vth = 0.45 V`: decision threshold for each input bit.
- `P_VREF_1_0_V_OUTPUT_FULL`: `vref = 1.0 V`: output full-scale/reference voltage.
- `P_VTH_0_45_V_DECISION_THRESHOLD_2`: - `vth = 0.45 V`: decision threshold for each input bit. - `vref = 1.0 V`: output full-scale/reference voltage.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: Use deterministic voltage-domain Verilog-A and voltage contributions only. It is acceptable to express sub-radix weights with portable real arithmetic such as `pow(1.8, k)`. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels.


The required trace names are: `time`, `vd0`, `vd1`, `vd2`, `vd3`, `vd4`, `vd5`, `vd6`, `vd7`, `vd8`, `vd9`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
