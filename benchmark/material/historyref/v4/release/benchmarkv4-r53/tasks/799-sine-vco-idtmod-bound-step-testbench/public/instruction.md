# Sine VCO With Idtmod And Bound Step Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Sine VCO With Idtmod And Bound Step` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sine_vco_idtmod_bound_step.va`:
  - Module `sine_vco_idtmod_bound_step` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `out` (output, electrical)
    - position 2: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sine_vco_idtmod_bound_step.va`
- DUT instance: `XDUT (vin out metric) sine_vco_idtmod_bound_step`
- Required saved public traces: `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sine_vco_idtmod_bound_step.center_freq` defaults to `20.0e6 from (0:inf)`; valid range: finite; overrides center_freq.
- `sine_vco_idtmod_bound_step.vco_gain` defaults to `40.0e6 exclude 0.0`; valid range: finite; overrides vco_gain.
- `sine_vco_idtmod_bound_step.vco_amp` defaults to `0.9 from (0:inf)`; valid range: finite; overrides vco_amp.
- `sine_vco_idtmod_bound_step.vco_ppc` defaults to `40 from [4:inf)`; valid range: finite; overrides vco_ppc.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_FREQ_Q_CENTER_FREQ_VCO_GAIN`: exercise and make observable: `freq_q = center_freq + vco_gain * V(vin)` Required traces: `time`, `vin`, `out`, `metric`.
- `P_PHASE_Q_IDTMOD_FREQ_Q_0`: exercise and make observable: `phase_q = idtmod(freq_q, 0.0, 1.0)` (modulo-1 phase accumulator) Required traces: `time`, `vin`, `out`, `metric`.
- `P_OUT_VCO_AMP_SIN_M_TWO`: exercise and make observable: `out = vco_amp * sin(M_TWO_PI * phase_q)` (bipolar sine centered at `0 V`) Required traces: `time`, `vin`, `out`, `metric`.
- `P_METRIC_VCO_AMP_PHASE_Q_VOLTAGE`: exercise and make observable: `metric = vco_amp * phase_q` (voltage-coded instantaneous wrapped phase, `0 V` to `vco_amp`) Required traces: `time`, `vin`, `out`, `metric`.
- `P_CALL_BOUND_STEP_1_0_VCO`: exercise and make observable: call `$bound_step(1.0 / (vco_ppc * freq_q))` every step so the sine is resolved Required traces: `time`, `vin`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Use `idtmod()` as a voltage-domain phase integrator whose instantaneous
frequency is controlled by `vin`, and produce a continuous-time sine output.

This is a behavioral continuous-time task, not a conservative-current/KCL task.
Do not use `I(...)`, `ddt(...)`, or `idt(...)`.

The supplied DUT provides:
- `freq_q = center_freq + vco_gain * V(vin)`
- `phase_q = idtmod(freq_q, 0.0, 1.0)` (modulo-1 phase accumulator)
- `out = vco_amp * sin(M_TWO_PI * phase_q)` (bipolar sine centered at `0 V`)
- `metric = vco_amp * phase_q` (voltage-coded instantaneous wrapped phase, `0 V` to `vco_amp`)
- call `$bound_step(1.0 / (vco_ppc * freq_q))` every step so the sine is resolved
  with at least `vco_ppc` timepoints per cycle


The required trace names are: `time`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
