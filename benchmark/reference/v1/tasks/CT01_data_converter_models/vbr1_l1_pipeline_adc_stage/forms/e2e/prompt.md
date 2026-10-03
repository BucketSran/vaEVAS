# Task: vbr1_l1_pipeline_adc_stage:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Data Converter Models
- Base function: Pipeline ADC MDAC stage
- Domain: `voltage`
- Target artifact(s): `pipeline_stage.va`, `tb_pipeline_stage_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `pipeline_stage.va`, `tb_pipeline_stage_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `pipeline_stage.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "pipeline_stage.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `pipeline_stage.va` declares module `pipeline_stage` with positional ports: `VDD`, `VSS`, `PHI1`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=300n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `phi1`
- `phi2`
- `vin`
- `vres`
- `d1`
- `d0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `vref`
- `phi1`
- `phi2`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "pipeline_stage.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

IDUT (vdd vss phi1 phi2 vin vref vres d1 d0) pipeline_stage vth=0.45 vdd=0.9 tedge=200p

tran tran stop=300n maxstep=500p
save phi1 phi2 vin vres d1 d0
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `upper_middle_lower_regions_exercised`
- `sub_adc_decisions_match_thresholds`
- `residue_follows_gain_two_mdac_formula`
- `residue_output_bounded`

## Public L1 Behavior Contract

This row is one behavioral pipeline ADC stage. The public behavior must expose
the coarse sub-ADC decision and the residue:

- Use non-overlapping `phi1` and `phi2` sampling/transfer phases.
- Exercise upper, middle, and lower input regions across the 0 V to 0.9 V
  reference range.
- Drive `d1 d0` as the 2-bit sub-ADC decision for the sampled `vin`.
- Drive `vres` as the gain-of-two MDAC-style residue implied by the sampled
  input and coarse decision.
- Keep `vres` bounded in the public voltage range.

The expected public relation is: stable phase sample -> threshold decision on
`d1 d0` -> matching residue on `vres`.

## Output Contract

Return exactly these source artifacts:

- `pipeline_stage.va`
- `tb_pipeline_stage_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Create a pure voltage-domain 1.5-bit pipeline ADC MDAC stage and matching
Spectre testbench. The DUT samples `VIN` on `PHI1`, makes a sub-ADC decision on
`PHI2`, drives `D1/D0`, and outputs the gain-of-2 residue for the next stage.

Public behavior:

- upper region: `VIN - Vcm > VREF/4`, drive `D1=1`, `D0=0`,
  `VRES = Vcm + 2*(VIN - Vcm) - VREF/2`
- lower region: `VIN - Vcm < -VREF/4`, drive `D1=0`, `D0=0`,
  `VRES = Vcm + 2*(VIN - Vcm) + VREF/2`
- middle region: drive `D1=0`, `D0=1`,
  `VRES = Vcm + 2*(VIN - Vcm)`

The testbench must use non-overlapping `PHI1`/`PHI2`, exercise all three
regions, save `phi1`, `phi2`, `vin`, `vres`, `d1`, and `d0`, and keep all
behavior pure voltage-domain with `transition(...)`.
