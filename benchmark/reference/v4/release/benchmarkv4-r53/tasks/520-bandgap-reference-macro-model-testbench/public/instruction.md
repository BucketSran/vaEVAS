# Bandgap Reference Macro Model Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Bandgap Reference Macro Model` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `bandgap_reference_macro_model.va`:
  - Module `bandgap_reference_macro_model` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/bandgap_reference_macro_model.va`
- DUT instance: `XFB_DUT (clk rst vin out metric) bandgap_reference_macro_model`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `bandgap_reference_macro_model.tr` defaults to `1e-10` s; valid range: tr > 0; sets output and metric transition smoothing.
- `bandgap_reference_macro_model.vth` defaults to `0.45` V; valid range: finite real; sets the voltage-coded clk and rst threshold.
- `bandgap_reference_macro_model.vstart` defaults to `0.58` V; valid range: vstart > 0.05; sets the supply level required for startup and valid updates.
- `bandgap_reference_macro_model.vref` defaults to `0.55` V; valid range: vref >= 0; sets the nominal regulated reference target before line correction and clamping.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_AND_BROWNOUT`: exercise and make observable: Reset or vin below vstart forces out and metric to 0 V. Required traces: `time`, `rst`, `vin`, `out`, `metric`.
- `P_CLOCKED_FIRST_ORDER_SETTLING`: exercise and make observable: On eligible rising clock crossings, the held reference advances by 0.35 of the remaining error to the clamped line-corrected target. Required traces: `time`, `clk`, `rst`, `vin`, `out`.
- `P_TARGET_AND_OUTPUT_CLAMPS`: exercise and make observable: The line-corrected target is clamped to 0 through vin minus 0.05 V, and driven out remains within 0 through 0.9 V. Required traces: `time`, `vin`, `out`.
- `P_VALIDITY_ENCODING`: exercise and make observable: Metric is 0 V in reset or brownout, 0.2 V during startup below the 0.48 V validity threshold, and 0.9 V after the held reference exceeds it. Required traces: `time`, `rst`, `vin`, `out`, `metric`.
- `P_CLOCKED_HOLD`: exercise and make observable: Above startup, the reference state changes only on rising clock crossings and holds between samples. Required traces: `time`, `clk`, `vin`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `clk` and `rst` are voltage-coded logic signals, low near 0 V and high near 0.9 V.
- `vin` is a sub-1 V supply ramp for the reference macro.
- During reset or when `vin < vstart`, hold the reference state and `out` at
  0 V and drive `metric` to 0 V.
- On each rising `clk` crossing with reset low and `vin >= vstart`, compute the
  target reference as `vref + 0.020 * (vin - 0.75 V)`.
- Clamp that target so it is not below 0 V and not above `vin - 0.05 V`.
- Update the held reference state with first-order settling:
  `ref_next = ref_prev + 0.35 * (target - ref_prev)`.
- Clamp the driven `out` voltage to the `[0 V, 0.9 V]` signal range.
- During brownout below `vstart`, return `out` to 0 V and mark the reference
  invalid.
- Drive `metric` as a voltage-coded reference-valid observable: 0 V during
  reset/brownout, 0.9 V when the held reference exceeds 0.48 V, and 0.2 V
  after startup while the held reference has not yet exceeded 0.48 V.
- Keep the model pure voltage-domain behavioral Verilog-A. Do not use branch-current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
