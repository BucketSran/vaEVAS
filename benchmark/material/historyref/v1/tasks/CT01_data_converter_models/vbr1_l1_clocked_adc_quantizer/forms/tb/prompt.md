# Task: vbr1_l1_clocked_adc_quantizer:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Data Converter Models
- Base function: Clocked ADC quantizer
- Domain: `voltage`
- Target artifact(s): `tb_flash_adc_3b_ref.scs`
- Supplied/reference support artifact(s): `flash_adc_3b.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `flash_adc_3b.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "flash_adc_3b.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

- `transient_analysis_present`
- `public_observables_saved`
- `dut_or_system_instantiated`

## Public L1 Testbench Stimulus Contract

This TB row should exercise a clocked ADC quantizer, not only instantiate it:

- Drive `vin` as a slow monotonic ramp across the 0 V to 0.9 V input range.
- Drive `clk` as a periodic 0 V/0.9 V clock with many rising edges during the
  ramp.
- Hold the ramp slow enough that adjacent clock samples visit multiple
  quantization regions.
- Save `vin`, `clk`, and `dout2 dout1 dout0` exactly.
- Do not generate checker logic; the evaluator uses the saved waveform to see
  that the supplied quantizer is clocked and observable.

## Output Contract

Return exactly one source artifact named `tb_flash_adc_3b_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Clocked ADC quantizer Testbench Companion

Write a Spectre transient testbench for the `Clocked ADC quantizer` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the checker
- include or instantiate the Verilog-A behavioral module under test
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
