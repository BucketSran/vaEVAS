# Op-amp Feedback Settling Monitor Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Op-amp Feedback Settling Monitor` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `opamp_feedback_settling.va`:
  - Module `opamp_feedback_settling` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `gain_2` (inout, electrical)
    - position 5: `gain_1` (inout, electrical)
    - position 6: `gain_0` (inout, electrical)
    - position 7: `vout` (inout, electrical)
    - position 8: `error_metric` (inout, electrical)
    - position 9: `settled` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/opamp_feedback_settling.va`
- DUT instance: `XDUT (vin clk rst enable gain_2 gain_1 gain_0 vout error_metric settled) opamp_feedback_settling`
- Required saved public traces: `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `opamp_feedback_settling.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `opamp_feedback_settling.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `opamp_feedback_settling.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `opamp_feedback_settling.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `opamp_feedback_settling.gain_lsb` defaults to `0.5`; valid range: finite; overrides gain_lsb.
- `opamp_feedback_settling.alpha` defaults to `0.3`; valid range: finite; overrides alpha.
- `opamp_feedback_settling.settle_tol` defaults to `40e-3`; valid range: finite; overrides settle_tol.
- `opamp_feedback_settling.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `opamp_feedback_settling.tick` defaults to `250p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_ENABLE_IS`: exercise and make observable: On reset or while disabled drive vout=vcm, drive the zero-error encoding error_metric=vcm, clear settled to vss, and clear the settle counter. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`.
- `P_DECODE_GAIN_2_GAIN_0_INTO`: exercise and make observable: Poll every tick=250ps, decode code=4*gain_2+2*gain_1+gain_0, and compute target=clamp(vcm+(1+gain_lsb*code)*(vin-vcm),vss,vdd). Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`.
- `P_UPDATE_VOUT_ONCE_PER_RISING_CLK`: exercise and make observable: On each enabled rising clk edge update vout_next=clamp(vout+alpha*(target-vout),vss,vdd) and then error=target-vout_next. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`.
- `P_CLAMP_VOUT_TO_THE_RANGE_VSS`: exercise and make observable: Clamp `vout` to the range `vss` through `vdd`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`.
- `P_ERROR_METRIC_MUST_EXPOSE_THE_SIGNED`: exercise and make observable: Encode target-minus-output error as the vcm-centered public voltage error_metric=vcm+(target-vout_next), so vcm denotes zero error on active updates and during reset or disable. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`.
- `P_ASSERT_SETTLED_AFTER_THREE_CONSECUTIVE_UPDATES`: exercise and make observable: Increment the counter when abs(target-vout_next)<settle_tol, clear it otherwise, and assert settled=vdd at count three. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, drive `vout` and the zero-error encoding on `error_metric` to `vcm`, and clear `settled`.
- Decode `gain_2..gain_0` into a closed-loop target gain of at least unity.
- Update `vout` once per rising `clk` edge toward the target closed-loop output using `alpha`.
- Clamp `vout` to the range `vss` through `vdd`.
- `error_metric` must expose the target-minus-output error as a `vcm`-centered voltage code.
- Assert `settled` after three consecutive updates where the absolute error is below `settle_tol`.
- The output must move in the direction of the target after an input step unless already clamped.

Poll controls every `tick = 250 ps`. Decode
`code=4*gain_2+2*gain_1+gain_0` and, on each enabled rising edge, compute

`target = clamp(vcm + (1+gain_lsb*code)*(vin-vcm), vss, vdd)`

`vout_next = clamp(vout + alpha*(target-vout), vss, vdd)`

`error = target-vout_next`.

Drive `vout=vout_next` and encode the signed error on the public electrical
metric as `error_metric=vcm+error`; `vcm` therefore represents zero error.
Increment the settle counter when `abs(error)<settle_tol`, otherwise clear it,
and assert `settled=vdd` at count three. Reset or disable drives `vout=vcm`,
`error_metric=vcm`, and `settled=vss`, and clears the counter.


The required trace names are: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `settled`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
