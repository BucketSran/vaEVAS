# Task: vbr1_l2_reference_startup_enable_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Bias Reference and Power Management
- Base function: Reference startup/enable flow
- Domain: `voltage`
- Target artifact(s): `tb_reference_startup_enable_flow.scs`
- Supplied/reference support artifact(s): `reference_startup_enable_flow.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Reference startup/enable flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `reference_startup_enable_flow.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "reference_startup_enable_flow.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `reference_startup_enable_flow.va` declares module `reference_startup_enable_flow` with positional ports: `clk`, `rst`, `vdd_in`, `en`, `out`, `metric`, `supply_ok`, `enable_mon`, `state_mon`, `startup_mon`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=0.5n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vdd_in`
- `en`
- `out`
- `metric`
- `supply_ok`
- `enable_mon`
- `state_mon`
- `startup_mon`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vdd_in`
- `en`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_reference_startup_enable_flow.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvdd_in (vdd_in 0) vsource type=pwl wave=[0 0.15 9.9n 0.15 10n 0.70 53.9n 0.70 54n 0.20 62.9n 0.20 63n 0.70 80n 0.70]
Ven (en 0) vsource type=pwl wave=[0 0 23.9n 0 24n 0.9 80n 0.9]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "reference_startup_enable_flow.va"

XDUT (clk rst vdd_in en out metric supply_ok enable_mon state_mon startup_mon) reference_startup_enable_flow

tran tran stop=80n maxstep=0.5n
save clk rst vdd_in en out metric supply_ok enable_mon state_mon startup_mon
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `supply_good_and_enable_monitors_are_visible`
- `pre_enable_reference_is_held_low`
- `enabled_reference_startup_settles`
- `startup_progress_and_state_transition_visible`
- `supply_dip_resets_valid_status`
- `state_and_valid_status_recover_after_supply_return`

## Public L2 Behavior Contract

The testbench must expose a complete startup and recovery flow:

1. Drive `vdd_in` through supply-off, supply-good, supply-dip, and recovery
   plateaus.
2. Keep `en` low during the pre-enable supply-good window, then assert it for
   startup and keep it asserted through the supply dip/recovery.
3. Save `supply_ok`, `enable_mon`, `state_mon`, and `startup_mon` so the
   evaluator can distinguish supply detection, enable gating, startup progress,
   and valid/recovery state from the final reference output.
4. Do not generate checker logic; the evaluator checks the public waveform
   relation from saved nodes.

## Output Contract

Return exactly one source artifact named `tb_reference_startup_enable_flow.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Reference startup/enable flow (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Compose supply-good detection, enable gating, reference startup, and valid-status observation in one behavioral flow.

Module name: `reference_startup_enable_flow`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module reference_startup_enable_flow(clk, rst, vdd_in, en, out, metric, supply_ok, enable_mon, state_mon, startup_mon);
input clk, rst, vdd_in, en;
output out, metric, supply_ok, enable_mon, state_mon, startup_mon;
electrical clk, rst, vdd_in, en, out, metric, supply_ok, enable_mon, state_mon, startup_mon;
```

Signal contract:

clk and rst are voltage-coded logic signals. vdd_in is the public supply waveform and en is the public enable command. out is the reference startup voltage. metric marks valid settled reference status. supply_ok exposes supply-good detection, enable_mon exposes the enable latch, state_mon exposes off/disabled/startup/valid state, and startup_mon exposes startup progress.

Saved waveform columns:

```text
clk rst vdd_in en out metric supply_ok enable_mon state_mon startup_mon
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
