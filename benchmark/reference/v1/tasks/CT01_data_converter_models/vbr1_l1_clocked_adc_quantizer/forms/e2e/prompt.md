# Task: vbr1_l1_clocked_adc_quantizer:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Data Converter Models
- Base function: Clocked ADC quantizer
- Domain: `voltage`
- Target artifact(s): `flash_adc_3b.va`, `tb_flash_adc_3b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `flash_adc_3b.va`, `tb_flash_adc_3b_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `flash_adc_3b.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "flash_adc_3b.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `flash_adc_3b.va` declares module `flash_adc_3b` with positional ports: `VDD`, `VSS`, `VIN`, `CLK`, `DOUT2`, `DOUT1`, `DOUT0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=820n maxstep=2n
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `dout2`
- `dout1`
- `dout0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `vin`
- `clk`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "flash_adc_3b.va"

Vvdd (vdd 0) vsource dc=0.9 type=dc
Vvss (vss 0) vsource dc=0.0 type=dc

IDUT (vdd vss vin clk dout2 dout1 dout0) flash_adc_3b vrefp=0.9 vrefn=0.0 vth=0.45 tedge=100p

tran tran stop=820n maxstep=2n
save vin clk dout2 dout1 dout0
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `flash_adc_all_8_codes_present`
- `flash_adc_monotonic_with_ramp`

## Output Contract

Return exactly these source artifacts:

- `flash_adc_3b.va`
- `tb_flash_adc_3b_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `flash_adc_3b` and one minimal voltage-domain Spectre transient testbench.

# Task: flash_adc_3b_smoke

## Objective

Create a pure voltage-domain 3-bit flash ADC behavioral model. The testbench must sweep the input
across the full reference range and produce all 8 output codes after clocked sampling.

## DUT Contract

- Module name: `flash_adc_3b`
- Ports, all `electrical`, exactly in this order: `vdd`, `vss`, `vin`, `clk`, `dout2`, `dout1`, `dout0`
- Parameters:
  - `vrefp` real, default `0.9`
  - `vrefn` real, default `0.0`
  - `vth` real, default `0.45`
  - `tedge` real, default `100p`
- Behavior:
  - On each rising `clk` edge, compute a 3-bit code from `V(vin)`.
  - Full-scale range is `vrefn` to `vrefp`, divided into 8 equal bins.
  - Clamp the code to `[0, 7]`.
  - Drive `dout2` as MSB, `dout1`, and `dout0` as LSB.
  - Output HIGH should be `V(vdd)` and output LOW should be `V(vss)`.
  - Use `@(cross(V(clk) - vth, +1))` and `transition(...)`.

## Testbench Contract

- Use a 0.9 V supply and 0 V reference.
- Drive `vin` with a monotonic full-scale sweep from near `0` to near `0.9 V` within the final validation window.
- Drive `clk` with a pulse clock fast enough to sample all 8 ADC codes during the input sweep.
- Instantiate the DUT by positional ports.
- Save these exact scalar names: `vin`, `clk`, `dout2`, `dout1`, `dout0`.
- Include the generated DUT file `flash_adc_3b.va`.
