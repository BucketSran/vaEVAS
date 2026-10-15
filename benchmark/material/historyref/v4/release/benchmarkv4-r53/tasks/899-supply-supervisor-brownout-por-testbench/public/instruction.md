# Supply Supervisor with Brownout POR Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Supply Supervisor with Brownout POR` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `supply_supervisor_brownout_por.va`:
  - Module `supply_supervisor_brownout_por` (entry)
    - position 0: `vdd_sense` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `por_n` (output, electrical)
    - position 5: `pgood` (output, electrical)
    - position 6: `brownout` (output, electrical)
    - position 7: `delay_metric` (output, electrical)
    - position 8: `state_metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/supply_supervisor_brownout_por.va`
- DUT instance: `XDUT (vdd_sense clk rst enable por_n pgood brownout delay_metric state_metric) supply_supervisor_brownout_por release_cycles=4`
- Required saved public traces: `vdd_sense`, `clk`, `rst`, `enable`, `por_n`, `pgood`, `brownout`, `delay_metric`, `state_metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `supply_supervisor_brownout_por.voh` defaults to `0.9` V; valid range: voh > vol; sets logic high.
- `supply_supervisor_brownout_por.vol` defaults to `0.0` V; valid range: vol < voh; sets logic low.
- `supply_supervisor_brownout_por.vth` defaults to `0.45` V; valid range: vss < vth < vdd; sets the digital-voltage crossing threshold.
- `supply_supervisor_brownout_por.uvlo_rise` defaults to `0.72` V; valid range: uvlo_rise > uvlo_fall; sets brownout release threshold.
- `supply_supervisor_brownout_por.uvlo_fall` defaults to `0.64` V; valid range: uvlo_fall < uvlo_rise; sets brownout assertion threshold.
- `supply_supervisor_brownout_por.release_cycles` defaults to `4` cycles; valid range: release_cycles >= 1; sets consecutive good cycles before release.
- `supply_supervisor_brownout_por.tr` defaults to `1e-10` s; valid range: tr > 0; sets transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_SAFE`: exercise and make observable: Reset or disable asserts brownout, holds POR low, clears pgood and both metrics. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `enable`, `por_n`, `pgood`, `brownout`, `delay_metric`, `state_metric`.
- `P_UVLO_HYSTERESIS`: exercise and make observable: Supply below uvlo_fall enters brownout and supply must exceed uvlo_rise to leave it. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `enable`, `por_n`, `pgood`, `brownout`, `delay_metric`, `state_metric`.
- `P_RELEASE_DELAY`: exercise and make observable: POR and pgood assert only after release_cycles consecutive good rising clock edges. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `enable`, `por_n`, `pgood`, `brownout`, `delay_metric`, `state_metric`.
- `P_DIP_RESTART`: exercise and make observable: A supply dip below uvlo_fall immediately reasserts brownout and clears release progress. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `enable`, `por_n`, `pgood`, `brownout`, `delay_metric`, `state_metric`.
- `P_STATE_METRICS`: exercise and make observable: Delay and state metrics report the saturated release count and four public supervisor states. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `enable`, `por_n`, `pgood`, `brownout`, `delay_metric`, `state_metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, assert brownout, deassert `pgood`, drive `por_n` low, and clear delay/state metrics.
- Apply hysteresis to `vdd_sense`: enter brownout below `uvlo_fall` and leave brownout only after `vdd_sense` rises above `uvlo_rise`.
- After leaving brownout, count consecutive rising `clk` edges while the supply remains above `uvlo_rise`.
- Release `por_n` and assert `pgood` only after `release_cycles` consecutive good enabled cycles.
- If `vdd_sense` drops below `uvlo_fall`, immediately assert brownout, clear the release counter, deassert `pgood`, and drive `por_n` low.
- `delay_metric` must expose release count `k` as
  `vol + (voh - vol) * k / release_cycles`, saturated at `voh`.
- `state_metric` must map reset, brownout, counting, and released to
  `vol`, `vol + (voh - vol)/3`, `vol + 2*(voh - vol)/3`, and `voh`,
  respectively.


The required trace names are: `time`, `vdd_sense`, `clk`, `rst`, `enable`, `por_n`, `pgood`, `brownout`, `delay_metric`, `state_metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
