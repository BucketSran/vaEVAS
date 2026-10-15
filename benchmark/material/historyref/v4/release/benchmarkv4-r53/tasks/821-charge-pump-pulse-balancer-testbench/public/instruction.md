# Charge-pump Pulse Balancer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Charge-pump Pulse Balancer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `charge_pump_pulse_balancer.va`:
  - Module `charge_pump_pulse_balancer` (entry)
    - position 0: `up` (input, electrical)
    - position 1: `dn` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `vctrl` (output, electrical)
    - position 6: `imbalance_metric` (output, electrical)
    - position 7: `balanced` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/charge_pump_pulse_balancer.va`
- DUT instance: `XDUT (up dn clk rst enable vctrl imbalance_metric balanced) charge_pump_pulse_balancer`
- Required saved public traces: `up`, `dn`, `clk`, `rst`, `enable`, `vctrl`, `imbalance_metric`, `balanced`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `charge_pump_pulse_balancer.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `charge_pump_pulse_balancer.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `charge_pump_pulse_balancer.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `charge_pump_pulse_balancer.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `charge_pump_pulse_balancer.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `charge_pump_pulse_balancer.pump_step` defaults to `20e-3 from (0:inf)` V; valid range: positive; overrides pump_step.
- `charge_pump_pulse_balancer.balance_tol` defaults to `30e-3 from (0:inf)` V; valid range: positive; overrides balance_tol.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_DRIVE`: exercise and make observable: On reset or when disabled, drive `vctrl` to `vcm`, clear imbalance, and clear `balanced`. Required traces: `time`, `up`, `dn`, `clk`, `rst`, `enable`, `vctrl`, `imbalance_metric`, `balanced`.
- `P_ON_EACH_RISING_CLK_EDGE_OBSERVE`: exercise and make observable: On each rising `clk` edge, observe voltage-coded `up` and `dn` pulse states. Required traces: `time`, `up`, `dn`, `clk`, `rst`, `enable`, `vctrl`, `imbalance_metric`, `balanced`.
- `P_INCREASE_VCTRL_FOR_UP_ONLY_DECREASE`: exercise and make observable: Increase `vctrl` for UP-only, decrease it for DN-only, and hold for simultaneous or inactive pulses. Required traces: `time`, `up`, `dn`, `clk`, `rst`, `enable`, `vctrl`, `imbalance_metric`, `balanced`.
- `P_DRIVE_IMBALANCE_METRIC_FROM_THE_ACCUMULATED`: exercise and make observable: Drive `imbalance_metric` from the accumulated UP-minus-DN activity. Required traces: `time`, `up`, `dn`, `clk`, `rst`, `enable`, `vctrl`, `imbalance_metric`, `balanced`.
- `P_ASSERT_BALANCED_ONLY_WHEN_THE_RECENT`: exercise and make observable: Assert `balanced` only when the recent absolute imbalance is below `balance_tol`. Required traces: `time`, `up`, `dn`, `clk`, `rst`, `enable`, `vctrl`, `imbalance_metric`, `balanced`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive `vctrl` to `vcm`, clear imbalance, and clear `balanced`.
- On each rising `clk` edge, observe voltage-coded `up` and `dn` pulse states.
- Increase `vctrl` for UP-only, decrease it for DN-only, and hold for simultaneous or inactive pulses.
- Drive `imbalance_metric` from the accumulated UP-minus-DN activity.
- Assert `balanced` only when the recent absolute imbalance is below `balance_tol`.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `up`, `dn`, `clk`, `rst`, `enable`, `vctrl`, `imbalance_metric`, `balanced`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
