# Task: vbr1_l2_pipeline_adc_chain:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: Data Converter Models
- Base function: Pipeline ADC residue chain
- Domain: `voltage`
- Target artifact(s): `pipeline_adc_chain_4b.va`, `tb_pipeline_adc_chain_4b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Pipeline ADC residue chain. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate all target artifacts: `pipeline_adc_chain_4b.va`, `tb_pipeline_adc_chain_4b_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `pipeline_adc_chain_4b.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "pipeline_adc_chain_4b.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `pipeline_adc_chain_4b.va` declares module `pipeline_adc_chain_4b` with positional ports: `VDD`, `VSS`, `VIN`, `CLK`, `RES1`, `RES2`, `S1B1`, `S1B0`, `S2B1`, `S2B0`, `DOUT3`, `DOUT2`, `DOUT1`, `DOUT0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=200p
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `res1`
- `res2`
- `s1b1`
- `s1b0`
- `s2b1`
- `s2b0`
- `dout3`
- `dout2`
- `dout1`
- `dout0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clk`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "pipeline_adc_chain_4b.va"

Vvdd (vdd 0) vsource type=dc dc=0.9
Vvss (vss 0) vsource type=dc dc=0.0

IDUT (vdd vss vin clk res1 res2 s1b1 s1b0 s2b1 s2b0 dout3 dout2 dout1 dout0) pipeline_adc_chain_4b vrefp=0.9 vrefn=0.0 vth=0.45 tedge=100p

tran tran stop=170n maxstep=200p
save vin clk res1 res2 s1b1 s1b0 s2b1 s2b0 dout3 dout2 dout1 dout0
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `all_16_pipeline_codes_present`
- `stage1_residue_matches_coarse_decision`
- `stage2_residue_matches_backend_decision`
- `final_code_matches_stage_concatenation`
- `final_code_monotonic_with_vin`

## Public L2 Behavior Contract

This row is a two-stage behavioral pipeline ADC residue chain. It should expose
the intermediate stage decisions and residues, not only the final code.

1. Stage-1 coarse decision:
   - Quantize the sampled `vin` into a 2-bit stage-1 code using four bins over
     the 0 V to 0.9 V input range.
   - Drive `s1b1 s1b0` as 0 V/0.9 V logic bits.
   - Drive `res1` as the first-stage residue implied by the stage-1 bin center.

2. Stage-2 backend decision:
   - Quantize `res1` into a second 2-bit code.
   - Drive `s2b1 s2b0` as 0 V/0.9 V logic bits.
   - Drive `res2` as the second-stage residual error implied by the backend
     decision.

3. Final code:
   - Drive `dout3 dout2 dout1 dout0` as the concatenation of the stage-1 and
     stage-2 decisions.
   - The final code should be monotonic with the sampled input and cover all 16
     4-bit codes under the public testbench.

Use a single-sample behavioral mapping with no hidden latency, redundancy, or
digital correction. The public testbench should hold each `vin` point stable
before a rising `clk` edge and include representative points for all 16 final
code bins.

## Output Contract

Return exactly these source artifacts:

- `pipeline_adc_chain_4b.va`
- `tb_pipeline_adc_chain_4b_ref.scs`

Return each artifact as a separate fenced code block, with the Verilog-A block
first and the Spectre testbench block second. Do not omit either artifact,
rename files, or include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: pipeline_adc_chain_e2e

Create a pure voltage-domain compact two-stage 4-bit pipeline ADC chain and a
matching Spectre transient testbench. The model should represent a composed
converter flow, not a single isolated MDAC stage. Treat this as a single-sample
behavioral residue chain: do not add interstage sample latency, redundancy,
digital correction, or transistor-level MDAC settling effects.

## DUT Contract

- Module name: `pipeline_adc_chain_4b`
- Ports, all `electrical`, exactly in this order: `VDD`, `VSS`, `VIN`, `CLK`,
  `RES1`, `RES2`, `S1B1`, `S1B0`, `S2B1`, `S2B0`, `DOUT3`, `DOUT2`,
  `DOUT1`, `DOUT0`
- Parameters:
  - `vrefp` real, default `0.9`
  - `vrefn` real, default `0.0`
  - `vth` real, default `0.45`
  - `tedge` real, default `100p`
- Behavior:
  - On each rising `clk` edge, sample `vin` and update both behavioral stages
    for that sampled value.
  - Stage 1 performs a 2-bit coarse quantization over `vrefn..vrefp`.
    With the default 0 V to 0.9 V range, use thresholds at 0.225 V, 0.45 V,
    and 0.675 V, producing stage codes 0, 1, 2, and 3.
    In general, stage code `k` represents the bin
    `[vrefn + k*span/4, vrefn + (k+1)*span/4)`, except the last bin includes
    the top endpoint.
  - Stage 1 drives `s1b1:s1b0` and computes a residue:
    `res1 = midscale + 4*(vin_sample - stage1_bin_center)`, clipped to the
    reference range.
    Here `span = vrefp - vrefn`, `midscale = (vrefp + vrefn)/2`, and
    `stage1_bin_center = vrefn + (stage1_code + 0.5)*span/4`.
  - Stage 2 performs a 2-bit backend quantization of `res1`.
  - Stage 2 drives `s2b1:s2b0` and computes `res2` with the same bin-center
    residue equation.
    Use `stage2_bin_center = vrefn + (stage2_code + 0.5)*span/4` and
    `res2 = midscale + 4*(res1 - stage2_bin_center)`, clipped to the reference
    range.
  - The final code is the concatenation of stage 1 and stage 2 decisions:
    `dout3:dout2:dout1:dout0 = {s1b1, s1b0, s2b1, s2b0}`.
  - Use `@(cross(V(clk) - vth, +1))` and `transition(...)`.
  - Keep the implementation behavioral and voltage-domain only.

## Testbench Contract

- Use a 0.9 V supply.
- Drive `vin` through representative points in all 16 final 4-bit code bins.
- Alternate lower-half and upper-half points inside adjacent bins so the
  residue path is exercised, not only the final code output.
  One suitable public sequence is:
  `0.0140625, 0.0984375, 0.1265625, 0.2109375, 0.2390625, 0.3234375,
  0.3515625, 0.4359375, 0.4640625, 0.5484375, 0.5765625, 0.6609375,
  0.6890625, 0.7734375, 0.8015625, 0.8859375` volts.
- Drive `clk` so every input point is stable before a rising clock edge.
  Use at least 16 useful rising edges and keep each `vin` point stable until
  at least 0.8 ns after its sampling edge.
- Keep the PWL `vin` source on one physical line, or use explicit backslash
  continuation on every continued line. PWL timestamps must be strictly
  increasing, and each input value must be stable before the associated rising
  clock edge.
- Use `vsource type=dc dc=...` for supplies and parenthesized source syntax
  throughout the Spectre testbench.
- Instantiate the DUT by positional ports.
- Save exactly these scalar names: `vin`, `clk`, `res1`, `res2`, `s1b1`,
  `s1b0`, `s2b1`, `s2b0`, `dout3`, `dout2`, `dout1`, `dout0`.
- Include a transient `tran` analysis.
