# Task: vbr1_l2_pipeline_adc_chain:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Data Converter Models
- Base function: Pipeline ADC residue chain
- Domain: `voltage`
- Target artifact(s): `tb_pipeline_adc_chain_4b_ref.scs`
- Supplied/reference support artifact(s): `pipeline_adc_chain_4b.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Pipeline ADC residue chain. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `pipeline_adc_chain_4b.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "pipeline_adc_chain_4b.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

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

This row is a two-stage behavioral pipeline ADC residue chain. The testbench
must expose intermediate stage behavior, not only final-code coverage:

1. Drive one stable input point for every final 4-bit code bin over the 0 V to
   0.9 V range.
2. Hold each `vin` value stable before the corresponding rising `clk` edge.
3. Save `s1b1 s1b0` and `res1` so the evaluator can compare the first-stage
   coarse decision and residue.
4. Save `s2b1 s2b0` and `res2` so the evaluator can compare the backend
   decision and second residue.
5. Save `dout3 dout2 dout1 dout0` so the evaluator can check final-code
   coverage, concatenation, and monotonicity.

Use a compact single-sample transient schedule. Do not add interstage latency
or checker logic in the testbench; the evaluator checks the public waveforms.

## Output Contract

Return exactly one source artifact named `tb_pipeline_adc_chain_4b_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Pipeline ADC residue chain Testbench Companion

Write a Spectre transient testbench for a pure voltage-domain compact two-stage
4-bit pipeline ADC chain. The supplied DUT performs a 2-bit coarse
quantization, outputs the first residue, performs a 2-bit backend quantization,
and drives a final 4-bit code for the same sampled input. This is a
single-sample behavioral residue chain, not a latency/correction benchmark.

Public requirements:

- use a 0.9 V supply
- drive `vin` through representative points in all 16 final 4-bit code bins
- alternate lower-half and upper-half points inside adjacent bins so the
  residue path is exercised, not only the final code output
- drive `clk` so every input point is stable before a rising clock edge
- instantiate `pipeline_adc_chain_4b` by positional ports
- save exactly these scalar names: `vin`, `clk`, `res1`, `res2`, `s1b1`,
  `s1b0`, `s2b1`, `s2b0`, `dout3`, `dout2`, `dout1`, `dout0`
- include a transient `tran` analysis
- avoid transistor-level devices, AC/noise analysis, and current-domain solver assumptions
