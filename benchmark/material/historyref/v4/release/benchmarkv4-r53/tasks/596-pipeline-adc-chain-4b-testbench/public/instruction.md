# Pipeline ADC Chain 4b Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Pipeline ADC Chain 4b` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `pipeline_adc_chain_4b.va`:
  - Module `pipeline_adc_chain_4b` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `VIN` (input, electrical)
    - position 3: `CLK` (input, electrical)
    - position 4: `RES1` (output, electrical)
    - position 5: `RES2` (output, electrical)
    - position 6: `S1B1` (output, electrical)
    - position 7: `S1B0` (output, electrical)
    - position 8: `S2B1` (output, electrical)
    - position 9: `S2B0` (output, electrical)
    - position 10: `DOUT3` (output, electrical)
    - position 11: `DOUT2` (output, electrical)
    - position 12: `DOUT1` (output, electrical)
    - position 13: `DOUT0` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/pipeline_adc_chain_4b.va`
- DUT instance: `IDUT (vdd vss vin clk res1 res2 s1b1 s1b0 s2b1 s2b0 dout3 dout2 dout1 dout0) pipeline_adc_chain_4b tedge=100p vrefn=0.0 vrefp=0.9 vth=0.45`
- Required saved public traces: `vdd`, `vss`, `vin`, `clk`, `res1`, `res2`, `s1b1`, `s1b0`, `s2b1`, `s2b0`, `dout3`, `dout2`, `dout1`, `dout0`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `pipeline_adc_chain_4b.vrefp` defaults to `0.9` V; valid range: vrefp > vrefn; sets positive conversion reference.
- `pipeline_adc_chain_4b.vrefn` defaults to `0.0` V; valid range: vrefn < vrefp; sets negative conversion reference.
- `pipeline_adc_chain_4b.vth` defaults to `0.45` V; valid range: finite real within the intended clock logic range; sets voltage-coded clock and bit decision threshold.
- `pipeline_adc_chain_4b.tedge` defaults to `1e-10` s; valid range: tedge > 0; sets residue and bit-output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CLOCKED_SAMPLE_HOLD`: exercise and make observable: On each rising CLK crossing, the converter samples VIN and updates all stage residues and bits; outputs hold between conversions. Required traces: `time`, `clk`, `vin`, `res1`, `res2`, `s1b1`, `s1b0`, `s2b1`, `s2b0`, `dout3`, `dout2`, `dout1`, `dout0`.
- `P_STAGE1_DECISION`: exercise and make observable: Stage 1 clips VIN to vrefn through vrefp, selects the correct quarter-scale bin, and exposes the two-bit coarse decision on S1B1/S1B0. Required traces: `time`, `clk`, `vin`, `s1b1`, `s1b0`.
- `P_STAGE1_RESIDUE`: exercise and make observable: RES1 is four times the clipped sampled-input error from the selected stage-1 bin center, clipped to the conversion range. Required traces: `time`, `vin`, `s1b1`, `s1b0`, `res1`.
- `P_STAGE2_DECISION`: exercise and make observable: Stage 2 applies the same quarter-scale two-bit decision to RES1 and exposes it on S2B1/S2B0. Required traces: `time`, `res1`, `s2b1`, `s2b0`.
- `P_STAGE2_RESIDUE`: exercise and make observable: RES2 is four times the stage-2 input error from its selected bin center, clipped to the conversion range. Required traces: `time`, `res1`, `s2b1`, `s2b0`, `res2`.
- `P_FINAL_CODE_CONCATENATION`: exercise and make observable: DOUT3/DOUT2 equal the stage-1 bits and DOUT1/DOUT0 equal the stage-2 bits, using VDD for high and VSS for low. Required traces: `time`, `vdd`, `vss`, `s1b1`, `s1b0`, `s2b1`, `s2b0`, `dout3`, `dout2`, `dout1`, `dout0`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

This is an L2 pipeline-ADC residue-chain component. On each rising crossing of
`CLK`, clip `VIN` to the `vrefn`-to-`vrefp` range and perform a two-stage
2-bit/stage conversion.

Stage 1 makes a 2-bit coarse decision from the clipped input. It should output
that decision on `S1B1/S1B0`, compute the center of the selected quarter-scale
bin, amplify the input error from that center by four, and drive the clipped
first residue on `RES1`.

Stage 2 quantizes `RES1` with the same 2-bit quarter-scale rule. It should
output the backend decision on `S2B1/S2B0`, compute the second residue with the
same gain-of-four residue rule, and drive the clipped backend residue on
`RES2`.

The final output word is the stage-1 decision concatenated with the stage-2
decision: `DOUT3/DOUT2` are the stage-1 bits and `DOUT1/DOUT0` are the stage-2
bits. High logic outputs should be near `VDD`; low logic outputs should be near
`VSS`.

**Public Verification Context**

The public transient scenario drives representative points across all 16 final
4-bit code bins, alternates lower-half and upper-half points inside adjacent
bins, and observes `vin`, `clk`, `res1`, `res2`, the stage bits, and the final
code bits. Treat that scenario as observable verification context, not as values
to hard-code into the DUT.


The required trace names are: `time`, `vdd`, `vss`, `vin`, `clk`, `res1`, `res2`, `s1b1`, `s1b0`, `s2b1`, `s2b0`, `dout3`, `dout2`, `dout1`, `dout0`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
