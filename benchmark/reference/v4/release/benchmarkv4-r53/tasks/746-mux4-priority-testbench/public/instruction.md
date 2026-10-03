# Mux4 Priority Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Mux4 Priority` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `mux4_priority.va`:
  - Module `mux4_priority` (entry)
    - position 0: `sel0` (input, electrical)
    - position 1: `sel1` (input, electrical)
    - position 2: `in0` (input, electrical)
    - position 3: `in1` (input, electrical)
    - position 4: `in2` (input, electrical)
    - position 5: `in3` (input, electrical)
    - position 6: `out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/mux4_priority.va`
- DUT instance: `XDUT (sel0 sel1 in0 in1 in2 in3 out) mux4_priority`
- Required saved public traces: `in0`, `in1`, `in2`, `in3`, `out`, `sel0`, `sel1`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `mux4_priority.vth` defaults to `0.45`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DECODE_THE_SELECT_CODE_AS_SEL0`: exercise and make observable: Decode the select code as `sel0 + 2*sel1`. For code `0`, forward `in0` to `out`; for code `1`, forward `in1`; for code `2`, forward `in2`; for code `3`, forward `in3`. The selected analog voltage should pass through without quantization or rail coding. Required traces: `time`, `in0`, `in1`, `in2`, `in3`, `out`, `sel0`, `sel1`.
- `P_PROVIDE_OVERRIDEABLE_PUBLIC_PARAMETER_VTH_0`: exercise and make observable: Provide overrideable public parameter `vth = 0.45 V` as the decision threshold for `sel0` and `sel1`. Required traces: `time`, `in0`, `in1`, `in2`, `in3`, `out`, `sel0`, `sel1`.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: exercise and make observable: Use deterministic voltage-domain Verilog-A and voltage contributions only. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels. Required traces: `time`, `in0`, `in1`, `in2`, `in3`, `out`, `sel0`, `sel1`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_DECODE_THE_SELECT_CODE_AS_SEL0`: Decode the select code as `sel0 + 2*sel1`. For code `0`, forward `in0` to `out`; for code `1`, forward `in1`; for code `2`, forward `in2`; for code `3`, forward `in3`. The selected analog voltage should pass through without quantization or rail coding.
- `P_PROVIDE_OVERRIDEABLE_PUBLIC_PARAMETER_VTH_0`: Provide overrideable public parameter `vth = 0.45 V` as the decision threshold for `sel0` and `sel1`.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: Use deterministic voltage-domain Verilog-A and voltage contributions only. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels.


The required trace names are: `time`, `in0`, `in1`, `in2`, `in3`, `out`, `sel0`, `sel1`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
