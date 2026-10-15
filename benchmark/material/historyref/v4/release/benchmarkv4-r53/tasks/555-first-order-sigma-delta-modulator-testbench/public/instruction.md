# First Order Sigma Delta Modulator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `First Order Sigma Delta Modulator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `first_order_sigma_delta_modulator.va`:
  - Module `first_order_sigma_delta_modulator` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `vclk` (input, electrical)
    - position 2: `bitout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/first_order_sigma_delta_modulator.va`
- DUT instance: `XDUT (vin vclk bitout) first_order_sigma_delta_modulator`
- Required saved public traces: `vin`, `vclk`, `bitout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `first_order_sigma_delta_modulator.vth_clk` defaults to `0.45` V; valid range: vth_clk > 0; sets the rising-clock decision threshold.
- `first_order_sigma_delta_modulator.vh` defaults to `0.9` V; valid range: vh > 0; sets the one-bit output high level.
- `first_order_sigma_delta_modulator.vref` defaults to `1` V; valid range: vref > 0; sets the normalized one-bit feedback magnitude.
- `first_order_sigma_delta_modulator.tr` defaults to `2e-11` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_EDGE_UPDATE`: exercise and make observable: The one-bit output state updates only from accumulator decisions made on rising crossings of vclk through vth_clk. Required traces: `time`, `vin`, `vclk`, `bitout`.
- `P_FIRST_ORDER_FEEDBACK`: exercise and make observable: Each clocked decision reflects accumulation of the current normalized input minus the previous one-bit feedback state. Required traces: `time`, `vin`, `vclk`, `bitout`.
- `P_BINARY_OUTPUT`: exercise and make observable: bitout is voltage-coded low near 0 V or high near vh with finite transition smoothing. Required traces: `time`, `vclk`, `bitout`.
- `P_INPUT_DENSITY_ORDER`: exercise and make observable: Over a sufficiently long common observation interval, a larger constant vin produces a nondecreasing fraction of high output bits. Required traces: `time`, `vin`, `vclk`, `bitout`.
- `P_FEEDBACK_STABILITY`: exercise and make observable: For an in-range constant input, the output stream continues to alternate as needed rather than running away as an open-loop accumulator. Required traces: `time`, `vin`, `vclk`, `bitout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Maintain a first-order accumulator. On each rising crossing of `vclk`, update
the accumulator with the current normalized input minus the previous one-bit
feedback value. Publish the next output bit high when the updated accumulator
is nonnegative and low otherwise. The output stream should therefore have a
higher pulse density for larger `vin` values while keeping the accumulator
bounded by the feedback action.


The required trace names are: `time`, `vin`, `vclk`, `bitout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
