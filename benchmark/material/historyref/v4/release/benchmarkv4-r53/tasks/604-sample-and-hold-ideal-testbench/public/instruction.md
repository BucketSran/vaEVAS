# Ideal Sample And Hold Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Ideal Sample And Hold` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `source_sample_hold.va`:
  - Module `source_sample_hold` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `vout` (output, electrical)
    - position 2: `vclk` (input, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/source_sample_hold.va`
- DUT instance: `XDUT (vin vout vclk) source_sample_hold`
- Required saved public traces: `vclk`, `vin`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `source_sample_hold.vtrans_clk` defaults to `0.45` V; valid range: finite real; sets the rising vclk sampling threshold.
- `source_sample_hold.tr` defaults to `2e-11` s; valid range: tr >= 0; sets vout transition smoothing without changing the sampled value.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_EDGE_CAPTURE`: exercise and make observable: On each rising vclk crossing through vtrans_clk, vout captures the instantaneous vin value. Required traces: `time`, `vclk`, `vin`, `vout`.
- `P_INTEREDGE_HOLD`: exercise and make observable: The captured value holds until the next rising sampling event even when vin changes. Required traces: `time`, `vclk`, `vin`, `vout`.
- `P_NO_FALLING_EDGE_CAPTURE`: exercise and make observable: Falling vclk crossings do not update the held value. Required traces: `time`, `vclk`, `vin`, `vout`.
- `P_UNITY_SAMPLE_GAIN`: exercise and make observable: The held target equals the sampled vin without gain, offset, quantization, or rail remapping. Required traces: `time`, `vclk`, `vin`, `vout`.
- `P_PARAMETERIZED_THRESHOLD`: exercise and make observable: Legal vtrans_clk overrides move the sampling crossing threshold while preserving rising-edge capture and hold behavior. Required traces: `time`, `vclk`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising crossing of `vclk` through `vtrans_clk`, sample the instantaneous
input voltage `V(vin)`. Hold that sampled value until the next rising sampling
event and drive it on `vout`.


The required trace names are: `time`, `vclk`, `vin`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
