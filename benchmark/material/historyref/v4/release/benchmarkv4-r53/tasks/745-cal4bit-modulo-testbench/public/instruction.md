# CAL4bit Modulo Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `CAL4bit Modulo` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cal4bit_modulo.va`:
  - Module `cal4bit_modulo` (entry)
    - position 0: `ain` (input, electrical)
    - position 1: `d0` (output, electrical)
    - position 2: `d1` (output, electrical)
    - position 3: `d2` (output, electrical)
    - position 4: `d3` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/cal4bit_modulo.va`
- DUT instance: `XDUT (ain d0 d1 d2 d3) cal4bit_modulo`
- Required saved public traces: `ain`, `d0`, `d1`, `d2`, `d3`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cal4bit_modulo.vh` defaults to `0.9`; valid range: finite; overrides vh.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_FLOOR_V_AIN_TO_AN_INTEGER`: exercise and make observable: Floor `V(ain)` to an integer code, clamp the code to the valid 4-bit range `0..15`, and emit the clamped code on `d0..d3`. Active bits should be near `vh`; inactive bits should be near `0 V`. Required traces: `time`, `ain`, `d0`, `d1`, `d2`, `d3`.
- `P_PROVIDE_OVERRIDEABLE_PUBLIC_PARAMETER_VH_0`: exercise and make observable: Provide overrideable public parameter `vh = 0.9 V` for the output logic-high level. The output low level is `0 V`. Required traces: `time`, `ain`, `d0`, `d1`, `d2`, `d3`.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: exercise and make observable: Use deterministic voltage-domain Verilog-A and smooth voltage-coded output transitions. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels. Required traces: `time`, `ain`, `d0`, `d1`, `d2`, `d3`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_FLOOR_V_AIN_TO_AN_INTEGER`: Floor `V(ain)` to an integer code, clamp the code to the valid 4-bit range `0..15`, and emit the clamped code on `d0..d3`. Active bits should be near `vh`; inactive bits should be near `0 V`.
- `P_PROVIDE_OVERRIDEABLE_PUBLIC_PARAMETER_VH_0`: Provide overrideable public parameter `vh = 0.9 V` for the output logic-high level. The output low level is `0 V`.
- `P_USE_DETERMINISTIC_VOLTAGE_DOMAIN_VERILOG_A`: Use deterministic voltage-domain Verilog-A and smooth voltage-coded output transitions. Do not emit a testbench, checker logic, out-of-band test hooks, hard-code testbench sample points, use current contributions, transistor-level devices, `ddt()`, `idt()`, or simulator side channels.


The required trace names are: `time`, `ain`, `d0`, `d1`, `d2`, `d3`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
