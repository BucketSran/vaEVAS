# Edge Delay Line with Deglitch Window Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Edge Delay Line with Deglitch Window` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `edge_delay_line_deglitch.va`:
  - Module `edge_delay_line_deglitch` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `vout` (output, electrical)
    - position 4: `edge_valid` (output, electrical)
    - position 5: `rejected` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/edge_delay_line_deglitch.va`
- DUT instance: `XDUT (vin rst enable vout edge_valid rejected) edge_delay_line_deglitch`
- Required saved public traces: `vin`, `rst`, `enable`, `vout`, `edge_valid`, `rejected`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `edge_delay_line_deglitch.vdd` defaults to `0.9` V; valid range: finite real greater than vss; sets the logic-high target for vout, edge_valid, and rejected.
- `edge_delay_line_deglitch.vss` defaults to `0.0` V; valid range: finite real less than vdd; sets the cleared and logic-low target for all public outputs.
- `edge_delay_line_deglitch.vth` defaults to `0.45` V; valid range: vss < vth < vdd; sets the decision threshold for vin, rst, and enable.
- `edge_delay_line_deglitch.tick` defaults to `2.5e-10` s; valid range: tick > 0; sets the deterministic qualification and delay scheduling interval.
- `edge_delay_line_deglitch.delay_ticks` defaults to `4` ticks; valid range: 0 <= delay_ticks <= 200; sets the additional number of scheduling ticks between qualification and output emission.
- `edge_delay_line_deglitch.min_width_ticks` defaults to `3` ticks; valid range: 1 <= min_width_ticks <= 200; sets the number of stable scheduling ticks required to qualify an input edge.
- `edge_delay_line_deglitch.tr` defaults to `1e-10` s; valid range: tr > 0; sets rise and fall smoothing for all public voltage outputs.

Scored evaluation uses the published default parameter values; alternative parameter overrides are outside the scored behavior contract.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: When rst is above vth or enable is at or below vth, pending edge state is cancelled and vout, edge_valid, and rejected settle to vss no later than the next scheduling tick. Required traces: `time`, `rst`, `enable`, `vout`, `edge_valid`, `rejected`.
- `P_STABLE_EDGE_QUALIFICATION`: exercise and make observable: A rising or falling vin crossing through vth can qualify only when vin remains in the crossed-to logic state for min_width_ticks scheduling ticks while reset is inactive and the DUT is enabled. Required traces: `time`, `vin`, `rst`, `enable`, `vout`.
- `P_DELAYED_EDGE_EMISSION`: exercise and make observable: After an input edge qualifies, vout changes to the corresponding vdd or vss target only after the additional delay_ticks scheduling interval and does not change early. Required traces: `time`, `vin`, `vout`.
- `P_NARROW_GLITCH_REJECTION`: exercise and make observable: If vin reverses before a pending edge completes qualification, that edge does not update vout and rejected produces a bounded high pulse. Required traces: `time`, `vin`, `vout`, `rejected`.
- `P_VALID_EMISSION_PULSE`: exercise and make observable: Each qualified delayed update of vout produces one bounded high pulse on edge_valid, while rejected remains reserved for cancelled narrow edges. Required traces: `time`, `vout`, `edge_valid`, `rejected`.
- `P_BIDIRECTIONAL_LEVELS`: exercise and make observable: Qualified rising and falling input edges can respectively drive vout toward vdd and vss, and all public outputs use tr-smoothed voltage transitions. Required traces: `time`, `vin`, `vout`, `edge_valid`, `rejected`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Reset or a low `enable` clears the delayed output and all pending edge state.
- An input edge must remain stable for `min_width_ticks` timer ticks before it can be emitted.
- A qualified edge updates `vout` after an additional `delay_ticks` timer ticks.
- A pending edge that reverses before qualification is rejected and must not update `vout`.
- `edge_valid` pulses when a qualified delayed edge updates the output.
- `rejected` pulses when a narrow glitch is rejected.


The required trace names are: `time`, `vin`, `rst`, `enable`, `vout`, `edge_valid`, `rejected`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
