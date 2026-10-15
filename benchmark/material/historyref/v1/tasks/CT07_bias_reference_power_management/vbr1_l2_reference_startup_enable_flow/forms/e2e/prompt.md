# Task: vbr1_l2_reference_startup_enable_flow:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: Bias Reference and Power Management
- Base function: Reference startup/enable flow
- Domain: `voltage`
- Target artifact(s): `reference_startup_enable_flow.va`, `tb_reference_startup_enable_flow.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Reference startup/enable flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate all target artifacts: `reference_startup_enable_flow.va`, `tb_reference_startup_enable_flow.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `reference_startup_enable_flow.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "reference_startup_enable_flow.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

Implement the flow as a visible startup sequence, not as a direct output lookup:

1. Supply-good and enable stage:
   - Interpret `vdd_in` as the public supply voltage and `en` as the public
     enable command.
   - Drive `supply_ok` high only when `vdd_in` is above the supply-good
     threshold.
   - Drive `enable_mon` high only when `en` is asserted.

2. Reference startup stage:
   - Hold `out` low while supply is off or enable is low.
   - After supply-good and enable are both asserted, let `out` settle gradually
     toward the reference target around 0.55 V.
   - Treat `out` as the analog reference voltage. Treat `metric` as a
     voltage-coded valid-status flag, not as a copy of the 0.55 V reference
     level.
   - Drive `startup_mon` as a monotonic startup-progress observable.
   - Drive `state_mon` through off/disabled/startup/valid states, voltage-coded
     between 0 V and 0.9 V.

3. Recovery stage:
   - A public supply dip must clear `supply_ok`, reset startup progress, and
     pull `out`/`metric` low.
   - When the supply returns while enable remains high, the flow must restart
     and recover valid status.

Acceptable public behavioral abstraction:

- Use a simple clocked state machine. `state_mon` should make off/reset,
  disabled, startup, and valid states visibly distinguishable with monotonic
  voltage-coded levels between 0 V and 0.9 V.
- Drive `supply_ok` high only when `vdd_in` is above the public supply-good
  threshold, and low again during the supply dip.
- Drive `enable_mon` directly from the public enable input after reset and
  supply-good qualification.
- During startup, increase an internal progress counter or progress real value
  on clock edges. Drive `startup_mon` monotonically from 0 V toward 0.9 V while
  the reference starts.
- Drive `out` gradually toward about 0.55 V after supply-good and enable are
  true. Drive `metric` low during off/disabled/startup and high near 0.9 V only
  after the reference has settled enough to be considered valid.
- On reset or supply dip, clear the progress/state, pull `metric` low, and pull
  `out` back down before allowing a later restart.

## Output Contract

Return exactly these source artifacts:

- `reference_startup_enable_flow.va`
- `tb_reference_startup_enable_flow.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Reference startup/enable flow (end-to-end)

Write both the Verilog-A behavioral module and a Spectre transient testbench.

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
