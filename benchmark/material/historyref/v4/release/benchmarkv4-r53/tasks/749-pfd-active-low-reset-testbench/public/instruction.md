# PFD With External Active Low Reset Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `PFD With External Active Low Reset` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `pfd_active_low_reset.va`:
  - Module `pfd_active_low_reset` (entry)
    - position 0: `ref` (input, electrical)
    - position 1: `fb` (input, electrical)
    - position 2: `rstb` (input, electrical)
    - position 3: `up` (output, electrical)
    - position 4: `down` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/pfd_active_low_reset.va`
- DUT instance: `XDUT (ref fb rstb up down) pfd_active_low_reset`
- Required saved public traces: `down`, `fb`, `ref`, `rstb`, `up`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `pfd_active_low_reset.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `pfd_active_low_reset.vh` defaults to `0.9`; valid range: finite; overrides vh.
- `pfd_active_low_reset.reset_delay` defaults to `80p from [0:inf)`; valid range: finite; overrides reset_delay.
- `pfd_active_low_reset.tr` defaults to `10p from [0:inf)`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_WHEN_RSTB_IS_BELOW_VTH_CLEAR`: exercise and make observable: When `rstb` is below `vth`, clear both PFD states and hold both outputs low. While `rstb` is high, a rising crossing of `ref` asserts `up`, and a rising crossing of `fb` asserts `down`. Once both states have occurred, schedule a reset after `reset_delay` and clear both states at that timer event. The reset input must also clear a pending one-sided UP or DOWN state even if the opposite edge has not arrived. Required traces: `time`, `down`, `fb`, `ref`, `rstb`, `up`.
- `P_VTH_0_45_V_THRESHOLD_FOR`: exercise and make observable: `vth = 0.45 V`: threshold for `ref`, `fb`, and `rstb`. Required traces: `time`, `down`, `fb`, `ref`, `rstb`, `up`.
- `P_VH_0_9_V_LOGIC_HIGH`: exercise and make observable: `vh = 0.9 V`: logic-high output level. Required traces: `time`, `down`, `fb`, `ref`, `rstb`, `up`.
- `P_RESET_DELAY_80_PS_FROM_0`: exercise and make observable: `reset_delay = 80 ps from [0:inf)`: delay from the moment both detector states are asserted to the mutual reset event. Required traces: `time`, `down`, `fb`, `ref`, `rstb`, `up`.
- `P_TR_10_PS_FROM_0_INF`: exercise and make observable: `tr = 10 ps from [0:inf)`: output transition smoothing time. Required traces: `time`, `down`, `fb`, `ref`, `rstb`, `up`.
- `P_VTH_0_45_V_THRESHOLD_FOR_2`: exercise and make observable: - `vth = 0.45 V`: threshold for `ref`, `fb`, and `rstb`. - `vh = 0.9 V`: logic-high output level. - `reset_delay = 80 ps from [0:inf)`: delay from the moment both detector states are asserted to the mutual reset event. - `tr = 10 ps from [0:inf)`: output transition smoothing time. Required traces: `time`, `down`, `fb`, `ref`, `rstb`, `up`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_WHEN_RSTB_IS_BELOW_VTH_CLEAR`: When `rstb` is below `vth`, clear both PFD states and hold both outputs low. While `rstb` is high, a rising crossing of `ref` asserts `up`, and a rising crossing of `fb` asserts `down`. Once both states have occurred, schedule a reset after `reset_delay` and clear both states at that timer event. The reset input must also clear a pending one-sided UP or DOWN state even if the opposite edge has not arrived.
- `P_VTH_0_45_V_THRESHOLD_FOR`: `vth = 0.45 V`: threshold for `ref`, `fb`, and `rstb`.
- `P_VH_0_9_V_LOGIC_HIGH`: `vh = 0.9 V`: logic-high output level.
- `P_RESET_DELAY_80_PS_FROM_0`: `reset_delay = 80 ps from [0:inf)`: delay from the moment both detector states are asserted to the mutual reset event.
- `P_TR_10_PS_FROM_0_INF`: `tr = 10 ps from [0:inf)`: output transition smoothing time.
- `P_VTH_0_45_V_THRESHOLD_FOR_2`: - `vth = 0.45 V`: threshold for `ref`, `fb`, and `rstb`. - `vh = 0.9 V`: logic-high output level. - `reset_delay = 80 ps from [0:inf)`: delay from the moment both detector states are asserted to the mutual reset event. - `tr = 10 ps from [0:inf)`: output transition smoothing time.


The required trace names are: `time`, `down`, `fb`, `ref`, `rstb`, `up`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
