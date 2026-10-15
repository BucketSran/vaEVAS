# Task: vbr1_l2_complete_calibration_loop:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Calibration, DEM, and Control
- Base function: Complete calibration loop
- Domain: `voltage`
- Target artifact(s): `tb_complete_calibration_loop.scs`
- Supplied/reference support artifact(s): `complete_calibration_loop.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Complete calibration loop. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `complete_calibration_loop.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "complete_calibration_loop.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `complete_calibration_loop.va` declares module `complete_calibration_loop` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`, `trim_mon`, `residual_mon`.

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
- `trim_mon`
- `residual_mon`

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
ahdl_include "complete_calibration_loop.va"

XDUT (clk rst vin out metric trim_mon residual_mon) complete_calibration_loop

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric trim_mon residual_mon
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `raw_error_is_corrected`
- `bounded_negative_feedback_response`
- `metric_tracks_convergence`
- `trim_moves_opposite_to_error`
- `residual_monitor_tracks_correction`

## Public L2 Behavior Contract

This row is a complete calibration loop. The testbench must expose raw error,
negative-feedback correction, and convergence:

1. Drive `clk` as a 0 V/0.9 V periodic clock and assert/deassert reset before
   useful loop operation.
2. Drive `vin` around the 0.45 V center point with both positive and negative
   excursions.
3. Include a reset or restart interval so metric reset/reconvergence can be
   observed.
4. Save `clk rst vin out metric trim_mon residual_mon` exactly. `trim_mon`
   is the bounded calibration control/trim voltage, and `residual_mon` is the
   post-correction residual monitor around the 0.45 V center point.

The expected public relation is: input error excursions on `vin` are corrected
through a bounded opposite-direction `trim_mon` response and reduced
`residual_mon`, then through `out`, while `metric` tracks loop convergence. Do
not generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_complete_calibration_loop.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Complete calibration loop (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Close a simple calibration loop from error stimulus through controller and actuator output.

Module name: `complete_calibration_loop`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module complete_calibration_loop(clk, rst, vin, out, metric, trim_mon, residual_mon);
input clk, rst, vin;
output out, metric, trim_mon, residual_mon;
electrical clk, rst, vin, out, metric, trim_mon, residual_mon;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. vin is the external offset/error stimulus around 0.45 V. The internal controller drives correction opposite the measured residual error, trim_mon is the public bounded trim/control voltage, residual_mon is the post-correction residual monitor around 0.45 V, out is the bounded corrected plant response, and metric is high when out is close to 0.45 V.

Saved waveform columns:

```text
clk rst vin out metric trim_mon residual_mon
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
