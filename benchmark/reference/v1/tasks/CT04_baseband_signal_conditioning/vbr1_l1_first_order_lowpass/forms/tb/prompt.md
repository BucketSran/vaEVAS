# Task: vbr1_l1_first_order_lowpass:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: First-order lowpass
- Domain: `voltage`
- Target artifact(s): `tb_first_order_lowpass_ref.scs`
- Supplied/reference support artifact(s): `first_order_lowpass.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `first_order_lowpass.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "first_order_lowpass.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `first_order_lowpass.va` declares module `first_order_lowpass` with positional ports: `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=160n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_first_order_lowpass_ref.scs`.

```spectre
Vin (vin 0) vsource type=pwl wave=[0 0 20n 0 21n 0.8 160n 0.8]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "first_order_lowpass.va"

XDUT (vin vout) first_order_lowpass

tran tran stop=160n maxstep=500p
save vin vout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `input_step_exercised`
- `monotone_first_order_step_response`
- `lagged_response_not_passthrough`
- `vout_reaches_expected_late_level`
- `bounded_without_overshoot`

## Output Contract

Return exactly one source artifact named `tb_first_order_lowpass_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Spectre testbench for a timer-discretized first-order lowpass DUT. This is the CT04 easy-anchor dynamic primitive: the testbench should expose a single-state settling trajectory after a voltage step.

The DUT module is `first_order_lowpass` with ports `vin, vout`. Both ports are electrical voltage nodes. The candidate DUT file will be available as `first_order_lowpass.va`; include it with `ahdl_include` and instantiate the DUT using the exact module and port names.

The testbench must exercise:
- Use a 500 ps timer update with state `y += 0.025 * (V(vin) - y)`.
- Drive `vout` from the internal state with `transition()`.
- The response must be monotone and visibly slower than an instantaneous copy.

Stimulus and observability requirements:
- Apply a 0 to high step on `vin` and run long enough for the lowpass output to settle.
- Save `vin` and `vout` for fixed-time response checks.
