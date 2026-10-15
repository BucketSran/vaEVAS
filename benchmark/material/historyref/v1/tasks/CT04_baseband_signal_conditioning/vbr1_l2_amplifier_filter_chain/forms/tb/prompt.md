# Task: vbr1_l2_amplifier_filter_chain:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Baseband Signal Conditioning
- Base function: Amplifier/filter chain
- Domain: `voltage`
- Target artifact(s): `tb_amplifier_filter_chain.scs`
- Supplied/reference support artifact(s): `amplifier_filter_chain.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Amplifier/filter chain. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `amplifier_filter_chain.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "amplifier_filter_chain.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `amplifier_filter_chain.va` declares module `amplifier_filter_chain` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`, `preamp_mon`, `filt1_mon`, `filt2_mon`, `settle_metric`.

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
- `preamp_mon`
- `filt1_mon`
- `filt2_mon`
- `settle_metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_amplifier_filter_chain.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.45 8n 0.45 12n 0.9 28n 0.9 31n 0.45 37n 0.45 42n 0.1 58n 0.1 61n 0.45 67n 0.45 72n 0.85 80n 0.85]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "amplifier_filter_chain.va"

XDUT (clk rst vin out metric preamp_mon filt1_mon filt2_mon settle_metric) amplifier_filter_chain

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric preamp_mon filt1_mon filt2_mon settle_metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `amplified_input`
- `preamp_monitor_matches_metric`
- `two_pole_internal_lag_visible`
- `filtered_output_lags_input`
- `metric_tracks_settling`
- `settle_status_asserts_after_output_recovery`

## Public L2 Behavior Contract

This row is an amplifier plus two-pole filter chain. The testbench must expose
the pre-filter amplified target, both internal filter states, and the lagged
filtered output:

1. Drive reset high initially, then release reset before the useful stimulus
   windows.
2. Drive `vin` through high, midscale, and low plateaus.
3. Save `metric`/`preamp_mon` as the pre-filter amplified target, `filt1_mon`
   and `filt2_mon` as the internal filter states, `out` as the second-pole
   output, and `settle_metric` as the settled-status observable.
4. Hold each input plateau long enough that the target moves first, the first
   pole follows, and the second pole/output visibly follows with settling lag.

The expected public relation is: `metric`/`preamp_mon` should jump quickly to
the bounded gain-stage target, `filt1_mon` should lag that target, and
`filt2_mon`/`out` should lag `filt1_mon`. Do not generate checker logic; the
evaluator checks amplification, internal lag, and settling from saved waveforms.

## Output Contract

Return exactly one source artifact named `tb_amplifier_filter_chain.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Amplifier/filter chain (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Combine a gain block and low-pass filter; expose the bounded pre-filter amplified target on metric so out can be checked for lagged settling.

Module name: `amplifier_filter_chain`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module amplifier_filter_chain(clk, rst, vin, out, metric, preamp_mon, filt1_mon, filt2_mon, settle_metric);
input clk, rst, vin;
output out, metric, preamp_mon, filt1_mon, filt2_mon, settle_metric;
electrical clk, rst, vin, out, metric, preamp_mon, filt1_mon, filt2_mon, settle_metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is an analog voltage stimulus. metric and preamp_mon expose the bounded pre-filter amplified target. filt1_mon and filt2_mon expose the two internal low-pass states. out is the bounded filtered voltage derived from the second pole. settle_metric is a voltage-coded settled-status observable.

Saved waveform columns:

```text
clk rst vin out metric preamp_mon filt1_mon filt2_mon settle_metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
