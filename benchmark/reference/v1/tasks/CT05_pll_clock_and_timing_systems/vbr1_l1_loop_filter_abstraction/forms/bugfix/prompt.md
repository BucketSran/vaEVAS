# Task: vbr1_l1_loop_filter_abstraction:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Sampled loop-filter abstraction
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_loop_filter_abstraction.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `loop_filter_abstraction` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.
- `dut_fixed.va` declares module `loop_filter_abstraction` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=0.5n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vin`
- `out`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `proportional_step_decays`
- `integral_residual_accumulates`
- `metric_asserts_after_valid_updates`
- `reset_clears_integrator`
- `filtered_output_bounded`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Sampled loop-filter abstraction (bugfix)

Repair the supplied buggy Verilog-A implementation using the public behavior checks and task description above. Treat the failing implementation as an observable mismatch; infer the repair from the source and public behavior rather than assuming a named root cause.

Behavioral intent:

Approximate the continuous-time proportional/integral loop-filter trend with sampled voltage-domain state updates on clock edges.

Module name: `loop_filter_abstraction`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a sampled/event-driven behavioral abstraction of the loop-filter control trend. It must not require current-domain charge storage, true continuous-time RC integration, or KCL/KVL solving.

Public port contract:

```verilog
module loop_filter_abstraction(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is a signed loop-error stimulus around 0.45 V. out is a bounded loop-control voltage. metric is a voltage-coded update/convergence observable.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
