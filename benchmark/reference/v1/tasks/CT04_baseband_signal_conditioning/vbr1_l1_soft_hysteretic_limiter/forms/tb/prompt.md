# Task: vbr1_l1_soft_hysteretic_limiter:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Soft/hysteretic limiter
- Domain: `voltage`
- Target artifact(s): `tb_soft_hysteretic_limiter.scs`
- Supplied/reference support artifact(s): `soft_hysteretic_limiter.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `soft_hysteretic_limiter.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "soft_hysteretic_limiter.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `soft_hysteretic_limiter.va` declares module `soft_hysteretic_limiter` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "soft_hysteretic_limiter.va"

XDUT (clk rst vin out metric) soft_hysteretic_limiter

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `smooth_limiting`
- `hysteresis_state_memory`
- `bounded_output`

## Public Stimulus Phases

Exercise the limiter with stable post-reset windows for these public phases:

| Phase | `vin` intent | Expected observable behavior |
|---|---|---|
| High excursion | drive `vin` above the upper threshold | `out` compresses near the high limited level and `metric` goes high |
| Mid hold after high | return `vin` near midscale | the high-memory state remains visible |
| Low excursion | drive `vin` below the lower threshold | `out` compresses near the low limited level and `metric` goes low |
| Mid hold after low | return `vin` near midscale | the low-memory state remains visible |

Keep reset release, clock edges, and `vin` changes separated enough that each
phase has settled saved samples within the 80 ns run.

Use this public phase timing so each behavior is visible in stable waveform
windows:

- Release reset before 10 ns.
- Use a clock period of about 4 ns, or otherwise ensure at least one rising
  edge occurs after each new `vin` phase begins and before that phase's public
  measurement window.
- High excursion: set `vin` above the upper threshold, around 0.80 V, before
  the 16-24 ns measurement window begins. For example, start the high excursion
  around 11.5-12 ns so a rising clock edge can latch the high state before
  16 ns.
- Mid hold after high: return `vin` near 0.50 V through the 31-36 ns window.
- Low excursion: set `vin` below the lower threshold, around 0.20 V, before
  the 46-55 ns measurement window begins. For example, start the low excursion
  around 43.5-44 ns so a rising clock edge can latch the low state before
  46 ns.
- Mid hold after low: return `vin` near 0.50 V through the 61-66 ns window.
- Drive logic high as 0.9 V, use parenthesized `vsource` source syntax, and
  write the analysis line exactly as `tran tran stop=80n maxstep=0.5n`.
- For each phase, make the PWL source hold a constant value across the listed
  measurement window. Do not ramp from one phase value to the next across the
  window; use short transitions outside the windows, such as 24.0 ns to 24.1 ns.

## Output Contract

Return exactly one source artifact named `tb_soft_hysteretic_limiter.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Soft/hysteretic limiter (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Limit a voltage signal with bounded compression and stateful hysteresis memory around high/low thresholds.

Module name: `soft_hysteretic_limiter`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module soft_hysteretic_limiter(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is an analog voltage stimulus. out is the bounded conditioned voltage. metric exposes the limiter hysteresis state: it goes high after upper-threshold excursions, low after lower-threshold excursions, and preserves that state during mid-level hold windows.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
