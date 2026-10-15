# Task: vbr1_l2_comparator_measurement_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Comparator and Decision Circuits
- Base function: Single-ramp comparator offset measurement flow
- Domain: `voltage`
- Target artifact(s): `tb_comparator_offset_search_ref.scs`
- Supplied/reference support artifact(s): `comparator_offset_search_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Single-ramp comparator offset measurement flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `comparator_offset_search_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "comparator_offset_search_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `comparator_offset_search_ref.va` declares module `comparator_offset_search_ref` with positional ports: `vdd`, `vss`, `inp`, `inn`, `outp`, `trip_v`, `offset_est`, `valid`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=100n maxstep=50p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `inp`
- `inn`
- `outp`
- `trip_v`
- `offset_est`
- `valid`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `inn`
- `inp`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "comparator_offset_search_ref.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

XDUT (vdd vss inp inn outp trip_v offset_est valid) comparator_offset_search_ref

tran tran stop=100n maxstep=50p errpreset=conservative
save inp inn outp trip_v offset_est valid
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `comparator_output_low_before_trip`
- `comparator_output_high_after_trip`
- `outp_first_trip_near_static_offset`
- `measurement_valid_latches_after_trip`
- `valid_first_assertion_near_trip`
- `trip_voltage_near_inn_plus_offset`
- `offset_estimate_near_static_offset`
- `measurement_outputs_hold_after_valid`

## Public L2 Behavior Contract

This row is a single-ramp comparator offset measurement flow. The testbench
must make the comparator trip and the measurement latch observable:

1. Drive `inn` as a stable 0.500 V reference.
2. Drive `inp` as a monotonic ramp from about 0.490 V to about 0.520 V.
3. Give enough transient time before the trip for `outp` and `valid` to be low.
4. Give enough transient time after the trip for `valid` to be high and for
   `trip_v` and `offset_est` to hold their latched values.

The expected public relation is: the first `outp` rising transition occurs near
the 5 mV offset point, `valid` asserts after that same trip, `trip_v` holds the
trip input voltage, and `offset_est` holds the measured input-reference
difference. Do not generate checker logic; the evaluator checks these saved
waveforms.

## Output Contract

Return exactly one source artifact named `tb_comparator_offset_search_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Single-ramp comparator offset measurement flow Testbench Companion

Write a Spectre transient testbench for the `Single-ramp comparator offset measurement flow` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- instantiate `comparator_offset_search_ref` with ports `vdd vss inp inn outp trip_v offset_est valid`
- drive `inn` at 0.500 V and perform a single ramp of `inp` from 0.490 V to 0.520 V over the transient
- save exactly the public scalar observables needed by the checker: `inp`, `inn`, `outp`, `trip_v`, `offset_est`, and `valid`
- include the Verilog-A behavioral module under test
- exercise the crossing so `outp`, `valid`, `trip_v`, and `offset_est` all settle after the expected 5 mV offset trip point
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
