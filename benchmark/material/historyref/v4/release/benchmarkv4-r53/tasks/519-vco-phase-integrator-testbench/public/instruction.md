# VCO Phase Integrator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `VCO Phase Integrator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `vco_phase_integrator.va`:
  - Module `vco_phase_integrator` (entry)
    - position 0: `vctrl` (input, electrical)
    - position 1: `phase` (output, electrical)
    - position 2: `clk` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/vco_phase_integrator.va`
- DUT instance: `XDUT (vctrl phase clk) vco_phase_integrator`
- Required saved public traces: `vctrl`, `phase`, `clk`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `vco_phase_integrator.tr` defaults to `2e-10` s; valid range: tr > 0; sets phase and clock transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_PERIODIC_PHASE_UPDATE`: exercise and make observable: Phase state updates on the public 1 ns periodic schedule by 0.03 plus 0.09 times vctrl. Required traces: `time`, `vctrl`, `phase`.
- `P_WRAPPED_PHASE_RANGE`: exercise and make observable: The observable phase remains in the normalized range from 0 inclusive to 1 exclusive. Required traces: `time`, `phase`.
- `P_WRAP_TOGGLES_CLOCK`: exercise and make observable: Each phase wrap by one cycle toggles the voltage-coded clock between 0 V and 0.9 V. Required traces: `time`, `phase`, `clk`.
- `P_CONTROLLED_EDGE_RATE`: exercise and make observable: A sustained higher vctrl produces more clock toggles over the same observation interval than a sustained lower vctrl. Required traces: `time`, `vctrl`, `clk`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Maintain a real phase state normalized to the range `[0, 1)`.
- Update the phase state on a periodic `1 ns` timer.
- At each update, increment phase by `0.03 + 0.09 * V(vctrl)`.
- When the phase reaches or exceeds `1.0`, wrap it by one cycle and toggle `clk`.
- Drive `phase` as the wrapped normalized phase voltage.
- Drive `clk` as a smoothed `0 V` / `0.9 V` voltage-coded clock.
- The clock edge rate must increase when `vctrl` increases.


The required trace names are: `time`, `vctrl`, `phase`, `clk`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
