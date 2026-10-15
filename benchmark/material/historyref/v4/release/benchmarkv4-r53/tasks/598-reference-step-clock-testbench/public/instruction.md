# Reference Step Clock Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Reference Step Clock` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ref_step_clk.va`:
  - Module `ref_step_clk` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `CLK` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/ref_step_clk.va`
- DUT instance: `XREF (VDD VSS CLK) ref_step_clk period_post=19.5n period_pre=20n t_switch=2u tedge=100p`
- Required saved public traces: `VDD`, `VSS`, `CLK`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ref_step_clk.period_pre` defaults to `2e-08` s; valid range: period_pre > 0; sets the full clock period before t_switch.
- `ref_step_clk.period_post` defaults to `1.95e-08` s; valid range: period_post > 0; sets the full clock period for cycles scheduled after t_switch.
- `ref_step_clk.t_switch` defaults to `2e-06` s; valid range: t_switch >= 0; sets the cadence-change boundary.
- `ref_step_clk.tedge` defaults to `1e-10` s; valid range: tedge > 0; sets CLK rise and fall smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SUPPLY_REFERENCED_RAILS`: exercise and make observable: CLK low and high levels track VSS and VDD respectively. Required traces: `time`, `VDD`, `VSS`, `CLK`.
- `P_PRE_SWITCH_PERIOD`: exercise and make observable: Clock cycles before t_switch have full period period_pre. Required traces: `time`, `CLK`.
- `P_POST_SWITCH_PERIOD`: exercise and make observable: Clock cycles scheduled after t_switch have full period period_post. Required traces: `time`, `CLK`.
- `P_CADENCE_STEP`: exercise and make observable: The waveform changes cadence near t_switch without stopping, duplicating, or losing clock transitions. Required traces: `time`, `CLK`.
- `P_HALF_DUTY_CYCLE`: exercise and make observable: CLK duty cycle remains close to 50 percent on both sides of the cadence step. Required traces: `time`, `CLK`.
- `P_PARAMETERIZED_TIMING`: exercise and make observable: Nearby legal overrides of period_pre, period_post, t_switch, and tedge produce the corresponding periods, switch boundary, and edge smoothing. Required traces: `time`, `VDD`, `VSS`, `CLK`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The verification harness instantiates the supplied DUT directly and
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


The required trace names are: `time`, `VDD`, `VSS`, `CLK`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
