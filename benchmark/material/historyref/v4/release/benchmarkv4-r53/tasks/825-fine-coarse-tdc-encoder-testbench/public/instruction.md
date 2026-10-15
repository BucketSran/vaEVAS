# Fine/coarse TDC Encoder Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Fine/coarse TDC Encoder` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `fine_coarse_tdc_encoder_top.va`:
  - Module `fine_coarse_tdc_encoder_top` (entry)
    - position 0: `start` (inout, electrical)
    - position 1: `stop` (inout, electrical)
    - position 2: `ref_clk` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `enable` (inout, electrical)
    - position 5: `coarse_3` (inout, electrical)
    - position 6: `coarse_2` (inout, electrical)
    - position 7: `coarse_1` (inout, electrical)
    - position 8: `coarse_0` (inout, electrical)
    - position 9: `fine_metric` (inout, electrical)
    - position 10: `valid` (inout, electrical)
- Artifact `coarse_counter.va`:
  - Module `coarse_counter` (required_submodule)
    - position 0: `a` (inout, electrical)
    - position 1: `b` (inout, electrical)
- Artifact `fine_residual_metric.va`:
  - Module `fine_residual_metric` (required_submodule)
    - position 0: `a` (inout, electrical)
    - position 1: `b` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/fine_coarse_tdc_encoder_top.va`, `./dut/coarse_counter.va`, `./dut/fine_residual_metric.va`
- DUT instance: `XDUT (start stop ref_clk rst enable coarse_3 coarse_2 coarse_1 coarse_0 fine_metric valid) fine_coarse_tdc_encoder_top`
- Required saved public traces: `start`, `stop`, `ref_clk`, `rst`, `enable`, `coarse_3`, `coarse_2`, `coarse_1`, `coarse_0`, `fine_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `fine_coarse_tdc_encoder_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `fine_coarse_tdc_encoder_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `fine_coarse_tdc_encoder_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `fine_coarse_tdc_encoder_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `fine_coarse_tdc_encoder_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `coarse_counter.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `fine_residual_metric.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: exercise and make observable: On reset or when disabled, clear coarse code, fine metric, and `valid`. Required traces: `time`, `start`, `stop`, `ref_clk`, `rst`, `enable`, `coarse_3`, `coarse_2`, `coarse_1`, `coarse_0`, `fine_metric`, `valid`.
- `P_A_RISING_START_EDGE_ARMS_A`: exercise and make observable: A rising `start` edge arms a measurement and clears the coarse counter. Required traces: `time`, `start`, `stop`, `ref_clk`, `rst`, `enable`, `coarse_3`, `coarse_2`, `coarse_1`, `coarse_0`, `fine_metric`, `valid`.
- `P_COUNT_RISING_REF_CLK_EDGES_UNTIL`: exercise and make observable: Count rising `ref_clk` edges until the first rising `stop` edge. Required traces: `time`, `start`, `stop`, `ref_clk`, `rst`, `enable`, `coarse_3`, `coarse_2`, `coarse_1`, `coarse_0`, `fine_metric`, `valid`.
- `P_LATCH_THE_COARSE_COUNT_INTO_COARSE`: exercise and make observable: Latch the coarse count into `coarse_3..coarse_0` and expose a fine residual proxy on `fine_metric`. Required traces: `time`, `start`, `stop`, `ref_clk`, `rst`, `enable`, `coarse_3`, `coarse_2`, `coarse_1`, `coarse_0`, `fine_metric`, `valid`.
- `P_ASSERT_VALID_ONLY_AFTER_THE_STOP`: exercise and make observable: Assert `valid` only after the stop edge completes the measurement. Required traces: `time`, `start`, `stop`, `ref_clk`, `rst`, `enable`, `coarse_3`, `coarse_2`, `coarse_1`, `coarse_0`, `fine_metric`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear coarse code, fine metric, and `valid`.
- A rising `start` edge arms a measurement and clears the coarse counter.
- Count rising `ref_clk` edges until the first rising `stop` edge.
- Latch the coarse count into `coarse_3..coarse_0` and expose a fine residual proxy on `fine_metric`.
- Assert `valid` only after the stop edge completes the measurement.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `start`, `stop`, `ref_clk`, `rst`, `enable`, `coarse_3`, `coarse_2`, `coarse_1`, `coarse_0`, `fine_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
