# Gain Trim Controller Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Gain Trim Controller` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `gain_trim_controller.va`:
  - Module `gain_trim_controller` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `meas` (input, electrical)
    - position 3: `target` (input, electrical)
    - position 4: `gain_ctrl` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/gain_trim_controller.va`
- DUT instance: `XDUT (clk rst meas target gain_ctrl) gain_trim_controller`
- Required saved public traces: `clk`, `rst`, `meas`, `target`, `gain_ctrl`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `gain_trim_controller.vth` defaults to `0.45` V; valid range: vth > 0; sets clk and rst decision threshold.
- `gain_trim_controller.tr` defaults to `5e-10` s; valid range: tr > 0; sets gain_ctrl transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_AND_RESET`: exercise and make observable: gain_ctrl initializes to 0.30 V and returns to 0.30 V on a rising clk edge while rst is high. Required traces: `time`, `clk`, `rst`, `gain_ctrl`.
- `P_ERROR_DIRECTION`: exercise and make observable: On rising clk edges, gain_ctrl increases by 0.05 V below target-0.02 V and decreases by 0.05 V above target+0.02 V. Required traces: `time`, `clk`, `rst`, `meas`, `target`, `gain_ctrl`.
- `P_DEADBAND_HOLD`: exercise and make observable: gain_ctrl holds when meas is within the inclusive target deadband. Required traces: `time`, `clk`, `meas`, `target`, `gain_ctrl`.
- `P_CONTROL_CLAMP`: exercise and make observable: gain_ctrl remains within the inclusive 0.05 V to 0.85 V range. Required traces: `time`, `gain_ctrl`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize `gain_ctrl` to 0.30 V before the first clocked update.
- Treat `clk` and `rst` as voltage-coded logic with threshold `vth`.
- On every rising crossing of `clk` through `vth`, update the internal
  control state.
- Reset `gain_ctrl` to 0.30 V on a rising `clk` while `rst` is above `vth`.
- When `meas` is below `target - 0.02`, increase the control by 0.05 V; when above `target + 0.02`, decrease it by 0.05 V.
- Hold inside the deadband, clamp to 0.05 V to 0.85 V, and drive through `transition()`.


The required trace names are: `time`, `clk`, `rst`, `meas`, `target`, `gain_ctrl`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
