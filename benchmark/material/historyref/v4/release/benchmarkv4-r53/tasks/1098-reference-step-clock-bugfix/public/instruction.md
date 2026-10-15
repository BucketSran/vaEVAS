# Reference Step Clock Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `ref_step_clk.va`:
  - Module `ref_step_clk` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `CLK` (output, electrical)

## Public Parameter Contract

- `ref_step_clk.period_pre` defaults to `2e-08` s; valid range: period_pre > 0; sets the full clock period before t_switch.
- `ref_step_clk.period_post` defaults to `1.95e-08` s; valid range: period_post > 0; sets the full clock period for cycles scheduled after t_switch.
- `ref_step_clk.t_switch` defaults to `2e-06` s; valid range: t_switch >= 0; sets the cadence-change boundary.
- `ref_step_clk.tedge` defaults to `1e-10` s; valid range: tedge > 0; sets CLK rise and fall smoothing.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_SUPPLY_REFERENCED_RAILS`: restore: CLK low and high levels track VSS and VDD respectively. Required traces: `time`, `VDD`, `VSS`, `CLK`.
- `P_PRE_SWITCH_PERIOD`: restore: Clock cycles before t_switch have full period period_pre. Required traces: `time`, `CLK`.
- `P_POST_SWITCH_PERIOD`: restore: Clock cycles scheduled after t_switch have full period period_post. Required traces: `time`, `CLK`.
- `P_CADENCE_STEP`: restore: The waveform changes cadence near t_switch without stopping, duplicating, or losing clock transitions. Required traces: `time`, `CLK`.
- `P_HALF_DUTY_CYCLE`: restore: CLK duty cycle remains close to 50 percent on both sides of the cadence step. Required traces: `time`, `CLK`.
- `P_PARAMETERIZED_TIMING`: restore: Nearby legal overrides of period_pre, period_post, t_switch, and tedge produce the corresponding periods, switch boundary, and edge smoothing. Required traces: `time`, `VDD`, `VSS`, `CLK`.


The following canonical public behavior is normative for this derived form:

This task asks for the `ref_step_clk` behavioral module, not a Spectre
testbench. The verification harness instantiates this module directly and
checks the generated `CLK` waveform.

- Generate a voltage-coded square-wave clock on `CLK`.
- Use the `VDD` and `VSS` supplies as the high and low output rails.
- Before `t_switch`, use `period_pre` as the full clock period.
- Near the switching time, transition from the pre-step cadence to the
  post-step cadence using `period_post` for subsequent clock periods.
- Keep duty cycle close to 50% before and after the frequency step.
- Preserve the public parameters `period_pre`, `period_post`, `t_switch`, and
  `tedge`.

Public parameters and legal overrides:

| Parameter | Default | Unit / range | Contract |
| --- | ---: | --- | --- |
| `period_pre` | `20 ns` | time, `(0:inf)` | Full clock period before the frequency step. |
| `period_post` | `19.5 ns` | time, `(0:inf)` | Full clock period after the frequency step. |
| `t_switch` | `2 us` | time, `[0:inf)` | Time at which subsequent clock periods use `period_post`. |
| `tedge` | `100 ps` | time, `(0:inf)` | Rise/fall smoothing for the voltage-coded clock output. |

A correct implementation should be parameterized by those public parameters
rather than hard-coding a fixed waveform. The observable behavior should remain
consistent when the verification harness instantiates nearby legal parameter
values, and should not rely on a fixed internal variable name or exact
implementation template.

Use voltage-coded logic with a mid-supply decision threshold where applicable,
drive high logic outputs near `VDD` and low outputs near `VSS`, and keep the
model pure behavioral Verilog-A. Do not use transistor-level devices, AC/noise
analysis, validation logic, validation-only hooks, or simulator-specific side channels.

Only `ref_step_clk.va` is graded as the candidate implementation.


## Modeling Constraints

- Generate a deterministic supply-referenced square wave with a parameterized frequency step.
- Use event-driven state and smoothed voltage contributions only.
- Do not hard-code validation stop times or sample windows, and do not use current contributions, transistor-level devices, validation hooks, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `ref_step_clk.va`.
Every supplied `.va` file is editable; do not add or omit files.
