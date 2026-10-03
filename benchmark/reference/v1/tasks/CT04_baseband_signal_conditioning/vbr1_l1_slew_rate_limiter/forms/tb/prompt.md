# Task: vbr1_l1_slew_rate_limiter:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Slew-rate limiter
- Domain: `voltage`
- Target artifact(s): `tb_slew_rate_limiter_ref.scs`
- Supplied/reference support artifact(s): `slew_rate_limiter.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `slew_rate_limiter.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "slew_rate_limiter.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `slew_rate_limiter.va` declares module `slew_rate_limiter` with positional ports: `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_slew_rate_limiter_ref.scs`.

```spectre
Vin (vin 0) vsource type=pwl wave=[0 0 20n 0 21n 0.8 95n 0.8 96n 0.1 170n 0.1]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "slew_rate_limiter.va"

XDUT (vin vout) slew_rate_limiter

tran tran stop=170n maxstep=500p
save vin vout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `input_up_down_steps_exercised`
- `rising_slew_is_limited`
- `high_level_eventually_reached`
- `falling_slew_is_limited`
- `low_level_eventually_reached`
- `lagged_response_not_passthrough`

## Output Contract

Return exactly one source artifact named `tb_slew_rate_limiter_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Spectre testbench for a discrete slew-rate limiter DUT.

The DUT module is `slew_rate_limiter` with ports `vin, vout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels. The candidate DUT file will be available as `slew_rate_limiter.va`; include it with `ahdl_include` and instantiate the DUT using the exact module and port names.

The testbench must exercise:
- Use a 1 ns timer update and move the internal output toward `vin` by at most 0.015 V per update.
- Limit both rising and falling changes and drive `vout` with `transition()`.

Stimulus and observability requirements:
- Apply a large upward step, hold, then a downward step.
- Save `vin` and `vout` to verify limited rising and falling slopes and eventual settling.
