# Ideal DAC 4bit Differential Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Ideal DAC 4bit Differential` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ideal_dac_4bit_differential.va`:
  - Module `ideal_dac_4bit_differential` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `digital` (input, electrical)
    - position 2: `vcm` (input, electrical)
    - position 3: `vop` (output, electrical)
    - position 4: `von` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/ideal_dac_4bit_differential.va`
- DUT instance: `XDUT (clk digital vcm vop von) ideal_dac_4bit_differential`
- Required saved public traces: `clk`, `digital`, `vcm`, `von`, `vop`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ideal_dac_4bit_differential.trise` defaults to `20p from [0:inf)`; valid range: finite; overrides trise.
- `ideal_dac_4bit_differential.tfall` defaults to `20p from [0:inf)`; valid range: finite; overrides tfall.
- `ideal_dac_4bit_differential.tdel` defaults to `0 from [0:inf)`; valid range: finite; overrides tdel.
- `ideal_dac_4bit_differential.vref` defaults to `1.0 from (0:inf)`; valid range: finite; overrides vref.
- `ideal_dac_4bit_differential.vtrans_clk` defaults to `0.5 from (0:inf)`; valid range: finite; overrides vtrans_clk.
- `ideal_dac_4bit_differential.levels` defaults to `16 from (0:inf)`; valid range: finite; overrides levels.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_FALLING_EDGE_CODE_SAMPLE`: exercise and make observable: Each falling `clk` crossing through `vtrans_clk` samples `digital`, clamps it to the valid code range, and holds the converted output until the next sample. Required traces: `time`, `clk`, `digital`, `vcm`, `von`, `vop`.
- `P_MIDRISE_DIFFERENTIAL_SCALE`: exercise and make observable: The sampled code maps to a mid-rise differential DAC level with the declared `levels` and `vref` scale. Required traces: `time`, `clk`, `digital`, `vcm`, `von`, `vop`.
- `P_OUTPUT_POLARITY_AND_COMMON_MODE`: exercise and make observable: `vop` and `von` are complementary about `vcm`, with positive differential polarity for larger sampled codes. Required traces: `time`, `clk`, `digital`, `vcm`, `von`, `vop`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each falling crossing of `clk` through `vtrans_clk`, sample the analog code on `digital`, clamp it into the valid code range, and convert it to a mid-rise differential DAC level over the span `-vref` to `+vref`. Drive `vop` and `von` complementarily around `V(vcm)`.


The required trace names are: `time`, `clk`, `digital`, `vcm`, `von`, `vop`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
