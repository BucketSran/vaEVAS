# CDR Eye Monitor Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `CDR Eye Monitor` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cdr_eye_monitor_top.va`:
  - Module `cdr_eye_monitor_top` (entry)
    - position 0: `data_in` (input, electrical)
    - position 1: `sample_clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `early` (output, electrical)
    - position 5: `late` (output, electrical)
    - position 6: `eye_metric` (output, electrical)
    - position 7: `lock_hint` (output, electrical)
    - position 8: `valid` (output, electrical)
- Artifact `edge_margin_sampler.va`:
  - Module `edge_margin_sampler` (required_submodule)
    - position 0: `data_in` (input, electrical)
    - position 1: `sample_clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `early` (output, electrical)
    - position 5: `late` (output, electrical)
    - position 6: `margin` (output, electrical)
    - position 7: `valid` (output, electrical)
- Artifact `eye_metric_filter.va`:
  - Module `eye_metric_filter` (required_submodule)
    - position 0: `sample_clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `margin` (input, electrical)
    - position 4: `sample_valid` (input, electrical)
    - position 5: `eye_metric` (output, electrical)
    - position 6: `lock_hint` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/cdr_eye_monitor_top.va`, `./dut/edge_margin_sampler.va`, `./dut/eye_metric_filter.va`
- DUT instance: `XDUT (data_in sample_clk rst enable early late eye_metric lock_hint valid) cdr_eye_monitor_top`
- Required saved public traces: `data_in`, `sample_clk`, `rst`, `enable`, `early`, `late`, `eye_metric`, `lock_hint`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cdr_eye_monitor_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `cdr_eye_monitor_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `cdr_eye_monitor_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `cdr_eye_monitor_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `cdr_eye_monitor_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `cdr_eye_monitor_top.eye_min` defaults to `0.55`; valid range: finite; overrides eye_min.
- `cdr_eye_monitor_top.edge_window` defaults to `600p from (0:inf)`; valid range: finite; overrides edge_window.
- `edge_margin_sampler.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `edge_margin_sampler.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `edge_margin_sampler.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `edge_margin_sampler.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `edge_margin_sampler.edge_window` defaults to `600p from (0:inf)`; valid range: finite; overrides edge_window.
- `eye_metric_filter.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `eye_metric_filter.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `eye_metric_filter.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `eye_metric_filter.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `eye_metric_filter.eye_min` defaults to `0.55`; valid range: finite; overrides eye_min.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: exercise and make observable: On reset or when disabled, clear early/late flags, eye metric, lock hint, and `valid`. Required traces: `time`, `data_in`, `sample_clk`, `rst`, `enable`, `early`, `late`, `eye_metric`, `lock_hint`, `valid`.
- `P_ON_EACH_SAMPLING_CLOCK_EDGE_COMPARE`: exercise and make observable: On each sampling-clock edge, compare the sampled data level with the previous sample. Required traces: `time`, `data_in`, `sample_clk`, `rst`, `enable`, `early`, `late`, `eye_metric`, `lock_hint`, `valid`.
- `P_RAISE_EARLY_OR_LATE_ACCORDING_TO`: exercise and make observable: Raise `early` or `late` according to the sign of the edge-position proxy around the sample instant. Required traces: `time`, `data_in`, `sample_clk`, `rst`, `enable`, `early`, `late`, `eye_metric`, `lock_hint`, `valid`.
- `P_DRIVE_EYE_METRIC_FROM_RECENT_TRANSITION`: exercise and make observable: Drive `eye_metric` from recent transition stability and sample margin. Required traces: `time`, `data_in`, `sample_clk`, `rst`, `enable`, `early`, `late`, `eye_metric`, `lock_hint`, `valid`.
- `P_ASSERT_LOCK_HINT_AFTER_FOUR_CONSECUTIVE`: exercise and make observable: Assert `lock_hint` after four consecutive samples with eye metric above `eye_min`. Required traces: `time`, `data_in`, `sample_clk`, `rst`, `enable`, `early`, `late`, `eye_metric`, `lock_hint`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear early/late flags, eye metric, lock hint, and `valid`.
- On each rising sampling-clock edge, produce a valid timing observation.
- Raise `early` for a data transition within `edge_window` before a sampling edge, and raise `late` for a transition within `edge_window` after it. Keep the flags mutually exclusive.
- Drive `eye_metric` from the measured sample margin; samples without a nearby transition represent an open-eye observation.
- Assert `lock_hint` after four consecutive samples with eye metric above `eye_min`.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `data_in`, `sample_clk`, `rst`, `enable`, `early`, `late`, `eye_metric`, `lock_hint`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
