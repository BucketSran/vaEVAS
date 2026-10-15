# Task: vbr1_l1_capacitive_weighted_sar_feedback_dac:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Data Converter Models
- Base function: Capacitive/weighted SAR feedback DAC
- Domain: `voltage`
- Target artifact(s): `cdac_cal.va`, `tb_cdac_cal_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `cdac_cal.va`, `tb_cdac_cal_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `cdac_cal.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "cdac_cal.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `cdac_cal.va` declares module `cdac_cal` with positional ports: `VDD`, `VSS`, `CLK`, `D9`, `D8`, `D7`, `D6`, `D5`, `D4`, `D3`, `D2`, `D1`, `D0`, `CAL0`, `CAL1`, `VDAC_P`, `VDAC_N`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=68n maxstep=20p
```

The release harness expects these exact public scalar observables:

- `CLK`
- `CAL0`
- `CAL1`
- `VDAC_P`
- `VDAC_N`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`
- `CLK`
- `D0`
- `D1`
- `D2`
- `D3`
- `D4`
- `D5`
- `D6`
- `D7`
- `D8`
- `D9`
- `CAL0`
- `CAL1`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cdac_cal.va"

Vvdd (VDD 0) vsource dc=0.9
Vvss (VSS 0) vsource dc=0

XDUT (VDD VSS CLK D9 D8 D7 D6 D5 D4 D3 D2 D1 D0 CAL0 CAL1 VDAC_P VDAC_N) cdac_cal

tran tran stop=68n maxstep=20p
save CLK CAL0 CAL1 VDAC_P VDAC_N
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `behavioral_module_present`
- `transient_analysis_present`
- `public_observables_saved`
- `sparse_10bit_code_stimulus_exercised`
- `binary_code_sets_nominal_dac_level`
- `calibration_bits_shift_feedback_level`
- `differential_outputs_move_complementarily`

## Output Contract

Return exactly these source artifacts:

- `cdac_cal.va`
- `tb_cdac_cal_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Capacitive/weighted SAR feedback DAC E2E Companion

Write both the Verilog-A behavioral module and a Spectre transient testbench for
the capacitive/weighted SAR feedback DAC.

Domain: pure voltage-domain behavioral Verilog-A.

Public DUT behavior:

- On each rising transition of `CLK`, sample `D9`...`D0`, `CAL0`, and `CAL1`
  against the mid-supply logic threshold.
- Convert `D9`...`D0` into an unsigned 10-bit `main_code`, with `D9` as MSB and
  `D0` as LSB.
- Convert the calibration inputs into `cal_code = CAL0 + 2*CAL1`.
- For this benchmark, model the redundant calibration contribution as
  `effective_code = main_code + 32*cal_code`.
- Drive complementary outputs around a 0.45 V common-mode under the public
  0.9 V supply. The intended differential behavior is
  `VDAC_P - VDAC_N = 0.6 * ((effective_code / 1023.0) - 0.5)`.
- Higher `effective_code` should raise `VDAC_P` relative to `VDAC_N`; lower
  `effective_code` should lower it.

Public testbench requirements:

- instantiate the behavioral Verilog-A module using the public positional port
  order
- include the public transient `tran` analysis
- use the required public stimulus pattern above
- save the exact public scalar observables listed above
- avoid transistor-level devices, AC/noise analysis, and current-domain solver
  assumptions
