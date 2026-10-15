# SAR Weighted Sum Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SAR Weighted Sum` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sar_weighted_sum.va`:
  - Module `sar_weighted_sum` (entry)
    - position 0: `D10` (input, electrical)
    - position 1: `D9` (input, electrical)
    - position 2: `D8` (input, electrical)
    - position 3: `D7` (input, electrical)
    - position 4: `D6` (input, electrical)
    - position 5: `D5` (input, electrical)
    - position 6: `D4` (input, electrical)
    - position 7: `D3` (input, electrical)
    - position 8: `D2` (input, electrical)
    - position 9: `D1` (input, electrical)
    - position 10: `D0` (input, electrical)
    - position 11: `VOUT` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sar_weighted_sum.va`
- DUT instance: `XDUT (d10 d9 d8 d7 d6 d5 d4 d3 d2 d1 d0 vout) sar_weighted_sum vth=0.65`
- Required saved public traces: `d10`, `d9`, `d8`, `d7`, `d6`, `d5`, `d4`, `d3`, `d2`, `d1`, `d0`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sar_weighted_sum.vth` defaults to `0.45` V; valid range: finite real value; sets the strict decision threshold independently applied to every D input.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_THRESHOLD_DECODE`: exercise and make observable: Each D input contributes logic 1 only while its voltage is strictly above vth; a value at or below vth contributes logic 0. Required traces: `time`, `d10`, `d9`, `d8`, `d7`, `d6`, `d5`, `d4`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_WEIGHT_ORDER`: exercise and make observable: The decoded contribution order is D10 at seven-eighths full scale, D9 at one-half, D8 at one-quarter, a 5:3 split across D7 and D6, then a binary tail from D5 through D0. Required traces: `time`, `d10`, `d9`, `d8`, `d7`, `d6`, `d5`, `d4`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_BIPOLAR_ENDPOINTS`: exercise and make observable: All decision inputs low produce -1 V, while all decision inputs high produce one 512-unit step below +1 V on the normalized bipolar scale. Required traces: `time`, `d10`, `d9`, `d8`, `d7`, `d6`, `d5`, `d4`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_MONOTONIC_CODE_WEIGHT`: exercise and make observable: Changing any decoded decision from low to high without lowering another decision cannot decrease VOUT. Required traces: `time`, `d10`, `d9`, `d8`, `d7`, `d6`, `d5`, `d4`, `d3`, `d2`, `d1`, `d0`, `vout`.
- `P_CONTINUOUS_DECODE`: exercise and make observable: VOUT continuously reflects the current threshold-decoded input combination without a clock, reset, or retained code state. Required traces: `time`, `d10`, `d9`, `d8`, `d7`, `d6`, `d5`, `d4`, `d3`, `d2`, `d1`, `d0`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Treat each `D*` input as logic `1` when its voltage is greater than `vth`,
  otherwise logic `0`.
- Implement a continuous SAR residue/source weighting law:
  - `D10` is the coarse residue bit with a seven-eighths full-scale weight.
  - `D9` and `D8` continue with half-scale and quarter-scale weights.
  - `D7` and `D6` split the next binary step in a 5:3 ratio to model a
    redundant SAR decision boundary.
  - `D5` through `D0` continue as the binary tail down to the unit LSB.
- Normalize the accumulated residue on a 512-unit bipolar scale so that all
  inputs low produce `-1 V`, the output is monotonic with added decision weight,
  and all inputs high land one 512-unit step below `+1 V`.
- Drive `VOUT` continuously from the decoded voltage-domain decision inputs.


The required trace names are: `time`, `d10`, `d9`, `d8`, `d7`, `d6`, `d5`, `d4`, `d3`, `d2`, `d1`, `d0`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
