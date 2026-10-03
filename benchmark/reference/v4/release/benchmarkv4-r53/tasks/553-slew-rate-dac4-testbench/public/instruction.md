# Slew Rate DAC4 Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Slew Rate DAC4` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `slew_rate_dac4.va`:
  - Module `slew_rate_dac4` (entry)
    - position 0: `d3` (input, electrical)
    - position 1: `d2` (input, electrical)
    - position 2: `d1` (input, electrical)
    - position 3: `d0` (input, electrical)
    - position 4: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/slew_rate_dac4.va`
- DUT instance: `XDUT (d3 d2 d1 d0 vout) slew_rate_dac4`
- Required saved public traces: `d3`, `d2`, `d1`, `d0`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `slew_rate_dac4.vth` defaults to `0.45` V; valid range: vth > 0; sets the decision threshold for all voltage-coded input bits.
- `slew_rate_dac4.vref` defaults to `1` V; valid range: vref > 0; sets the full-scale analog endpoint.
- `slew_rate_dac4.slewrate` defaults to `100000000` V/s; valid range: slewrate > 0; sets the maximum positive and negative magnitude of dvout/dt.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_BINARY_MAPPING`: exercise and make observable: d3 is the MSB and d0 is the LSB of an unsigned four-bit code whose target output is binary weighted. Required traces: `time`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_ENDPOINTS`: exercise and make observable: Code 0 targets 0 V and code 15 targets vref. Required traces: `time`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_CODE_MONOTONICITY`: exercise and make observable: A larger stable input code does not produce a lower settled output voltage. Required traces: `time`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_SLEW_LIMIT`: exercise and make observable: During a target change, the magnitude of the output slope does not exceed slewrate. Required traces: `time`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_SETTLED_TARGET`: exercise and make observable: After sufficient time at a stable code, vout reaches the corresponding code-to-vref target. Required traces: `time`, `d3`, `d2`, `d1`, `d0`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Interpret the four input voltages as an unsigned binary code using `vth`.
Map code zero to 0 V and code fifteen to `vref`, with monotonic binary-weighted
steps between those endpoints. Drive `vout` with slew-rate-limited analog
motion so large code changes ramp at the configured `slewrate` instead of
jumping immediately to the final value.


The required trace names are: `time`, `d3`, `d2`, `d1`, `d0`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
