# Fixed-frequency Oscillator Source Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Fixed-frequency Oscillator Source` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `fixed_frequency_oscillator_source.va`:
  - Module `fixed_frequency_oscillator_source` (entry)
    - position 0: `enable` (inout, electrical)
    - position 1: `rst` (inout, electrical)
    - position 2: `osc_out` (inout, electrical)
    - position 3: `period_metric` (inout, electrical)
    - position 4: `valid` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/fixed_frequency_oscillator_source.va`
- DUT instance: `XDUT (enable rst osc_out period_metric valid) fixed_frequency_oscillator_source`
- Required saved public traces: `enable`, `rst`, `osc_out`, `period_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `fixed_frequency_oscillator_source.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `fixed_frequency_oscillator_source.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `fixed_frequency_oscillator_source.period` defaults to `20e-9`; valid range: finite; overrides period.
- `fixed_frequency_oscillator_source.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `fixed_frequency_oscillator_source.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `fixed_frequency_oscillator_source.tick` defaults to `500p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_DRIVE`: exercise and make observable: On reset or when disabled, drive `osc_out`, `period_metric`, and `valid` low. Required traces: `time`, `enable`, `rst`, `osc_out`, `period_metric`, `valid`.
- `P_WHEN_ENABLED_GENERATE_A_PERIODIC_VOLTAGE`: exercise and make observable: When enabled, generate a periodic voltage-domain clock that toggles between `vss` and `vdd` with the configured period. Required traces: `time`, `enable`, `rst`, `osc_out`, `period_metric`, `valid`.
- `P_PERIOD_METRIC_MUST_EXPOSE_A_STABLE`: exercise and make observable: `period_metric` must expose a stable voltage-coded representation of the configured period after the first complete cycle. Required traces: `time`, `enable`, `rst`, `osc_out`, `period_metric`, `valid`.
- `P_ASSERT_VALID_AFTER_THE_FIRST_COMPLETE`: exercise and make observable: Assert `valid` after the first complete oscillator cycle following enable. Required traces: `time`, `enable`, `rst`, `osc_out`, `period_metric`, `valid`.
- `P_RESET_OR_DISABLE_MUST_RESTART_THE`: exercise and make observable: Reset or disable must restart the oscillator phase deterministically. Required traces: `time`, `enable`, `rst`, `osc_out`, `period_metric`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive `osc_out`, `period_metric`, and `valid` low.
- When enabled, generate a periodic voltage-domain clock that toggles between `vss` and `vdd` with the configured period.
- `period_metric` must expose a stable voltage-coded representation of the configured period after the first complete cycle.
- Assert `valid` after the first complete oscillator cycle following enable.
- Reset or disable must restart the oscillator phase deterministically.


The required trace names are: `time`, `enable`, `rst`, `osc_out`, `period_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
