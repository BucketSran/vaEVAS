# Task: vbr1_l1_capacitive_weighted_sar_feedback_dac:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Data Converter Models
- Base function: Capacitive/weighted SAR feedback DAC
- Domain: `voltage`
- Target artifact(s): `tb_cdac_cal_ref.scs`
- Supplied/reference support artifact(s): `cdac_cal.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `cdac_cal.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "cdac_cal.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

Vvdd (VDD 0) vsource type=dc dc=0.9
Vvss (VSS 0) vsource type=dc dc=0

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

- `transient_analysis_present`
- `public_observables_saved`
- `dut_or_system_instantiated`
- `sparse_10bit_code_stimulus_exercised`
- `calibration_stimulus_exercised`
- `differential_outputs_observable`

## Public Stimulus Schedule

Drive the first useful `CLK` rising edge at 5 ns, then repeat rising edges every
4 ns: 5 ns, 9 ns, 13 ns, ..., 65 ns. Before each rising edge, hold `D9..D0`,
`CAL0`, and `CAL1` stable for at least 0.5 ns. Keep them stable for at least
0.5 ns after the edge as well, so `VDAC_P` and `VDAC_N` have settled samples
about 0.25 ns after each rising edge.

Use this public sparse code/calibration sequence to cover low, mid, high, and
transition-adjacent 10-bit DAC regions:

| Edge index | 10-bit code | CAL value |
|---:|---:|---:|
| 0 | 0 | 0 |
| 1 | 1 | 1 |
| 2 | 2 | 2 |
| 3 | 3 | 3 |
| 4 | 7 | 0 |
| 5 | 15 | 1 |
| 6 | 16 | 2 |
| 7 | 32 | 3 |
| 8 | 64 | 0 |
| 9 | 128 | 1 |
| 10 | 256 | 2 |
| 11 | 512 | 3 |
| 12 | 255 | 0 |
| 13 | 511 | 1 |
| 14 | 767 | 2 |
| 15 | 1023 | 3 |

For each row, drive the 10-bit code as binary voltage levels on `D9..D0`
with logic low=0 V and logic high=0.9 V. Drive `CAL0/CAL1` as the two-bit
binary representation of the CAL value.

Map edge index 0 to the 5 ns rising edge, edge index 1 to the 9 ns rising edge,
and so on. A simple robust schedule is to update the data/calibration PWL values
around 1 ns before each listed rising edge, then hold them constant across the
edge and post-edge settling sample.

Use EVAS/Spectre-compatible source formatting:

- Use `//` comments or omit comments; do not use leading `*` comment lines.
- Keep each `vsource type=pwl wave=[...]` on one physical line, or use explicit
  backslash continuation at the end of every continued line.
- PWL timestamps must be strictly increasing. To change a code just before a
  clock edge, use a distinct setup time such as 3.5 ns before the 4 ns edge,
  not a duplicate timestamp.
- For each code row, hold all data and calibration bits stable across the setup
  and sampling window; do not ramp bit voltages across a clock edge.

## Output Contract

Return exactly one source artifact named `tb_cdac_cal_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Capacitive/weighted SAR feedback DAC TB Companion

Write a Spectre transient testbench for the supplied `cdac_cal` behavioral DUT.

Domain: pure voltage-domain behavioral Verilog-A.

Public testbench requirements:

- include or instantiate the supplied behavioral module under test using the
  public positional port order
- include the public transient `tran` analysis
- use the required public stimulus pattern above so both binary code changes and
  calibration-bit changes are exercised across low, mid, and high 10-bit codes
- save the exact public scalar observables listed above
- avoid transistor-level devices, AC/noise analysis, and current-domain solver
  assumptions
