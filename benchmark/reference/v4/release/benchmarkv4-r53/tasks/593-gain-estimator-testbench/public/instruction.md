# Gain Estimator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Gain Estimator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `gain_estimator.va`:
  - Module `gain_estimator` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `vinp` (input, electrical)
    - position 3: `vinn` (input, electrical)
    - position 4: `voutp` (input, electrical)
    - position 5: `voutn` (input, electrical)
    - position 6: `gain_out` (output, electrical)
    - position 7: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/gain_estimator.va`
- DUT instance: `XGAIN (vdd vss vinp vinn voutp voutn gain_out valid) gain_estimator gain_scale=10 min_input_span=0.02 sample_period=1n start_time=20n tedge=200p`
- Required saved public traces: `vdd`, `vss`, `vinp`, `vinn`, `voutp`, `voutn`, `gain_out`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `gain_estimator.sample_period` defaults to `1e-09` s; valid range: sample_period > 0; sets periodic extrema-sampling interval.
- `gain_estimator.start_time` defaults to `2e-08` s; valid range: start_time >= 0; sets when samples begin contributing to extrema.
- `gain_estimator.gain_scale` defaults to `10.0` V/V represented at full scale; valid range: gain_scale > 0; sets gain represented by full-scale gain_out.
- `gain_estimator.min_input_span` defaults to `0.02` V; valid range: min_input_span > 0; sets minimum input span required to assert valid.
- `gain_estimator.tedge` defaults to `2e-10` s; valid range: tedge > 0; sets gain_out and valid transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_START_TIME_GATING`: exercise and make observable: Samples before start_time do not contribute to measured input or output extrema and valid remains low. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`, `valid`.
- `P_PERIODIC_EXTREMA`: exercise and make observable: At each sample_period after start_time, the estimator updates minima and maxima of the input and output differential voltages. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`, `gain_out`, `valid`.
- `P_VALIDITY_THRESHOLD`: exercise and make observable: Valid remains rail-low until the observed input differential span exceeds min_input_span and remains rail-high afterwards. Required traces: `time`, `vdd`, `vss`, `vinp`, `vinn`, `valid`.
- `P_SPAN_RATIO`: exercise and make observable: Once valid, the measured gain equals output differential span divided by input differential span. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`, `gain_out`, `valid`.
- `P_NORMALIZED_GAIN_OUTPUT`: exercise and make observable: Gain_out equals the VDD-to-VSS rail span multiplied by measured gain divided by gain_scale. Required traces: `time`, `vdd`, `vss`, `gain_out`, `valid`.
- `P_EVENT_UPDATED_TARGETS`: exercise and make observable: Gain_out and valid reflect event-updated retained targets with finite smoothing rather than continuously varying transition inputs. Required traces: `time`, `gain_out`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Write a pure voltage-domain gain measurement helper. After a configurable start
time, sample the input and output differential spans on a periodic timer. Once
the observed input span is large enough, report the span ratio as a normalized
voltage metric and assert `valid`.

Public parameters:

- `sample_period = 1 ns`: timer interval for span updates.
- `start_time = 20 ns`: time before samples begin contributing to the spans.
- `gain_scale = 10.0`: gain value represented by a full-scale `gain_out`.
- `min_input_span = 0.02 V`: minimum observed input span before the metric is
  considered valid.
- `tedge = 200 ps`: rise/fall smoothing for `gain_out` and `valid`.

Required observable behavior:

- Track minimum and maximum values of `V(vinp,vinn)` and `V(voutp,voutn)` after
  `start_time`.
- Compute input and output spans from those extrema.
- When input span exceeds `min_input_span`, set `gain = output_span/input_span`
  and assert `valid`.
- Drive `gain_out` as `V(VDD,VSS) * gain / gain_scale`.
- Drive `valid` low before the metric is valid and high afterwards.

Use event-updated real state for the measured gain and validity flag. Smooth
only discrete metric targets with `transition()`. Do not generate a Spectre
testbench, waveform files, validation artifacts, transistor-level devices, current
contributions, `ddt()`, or `idt()`.


The required trace names are: `time`, `vdd`, `vss`, `vinp`, `vinn`, `voutp`, `voutn`, `gain_out`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
