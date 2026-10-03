# Amplifier Filter Chain Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Amplifier Filter Chain` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `amplifier_filter_chain.va`:
  - Module `amplifier_filter_chain` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)
    - position 5: `preamp_mon` (output, electrical)
    - position 6: `filt1_mon` (output, electrical)
    - position 7: `filt2_mon` (output, electrical)
    - position 8: `settle_metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/amplifier_filter_chain.va`
- DUT instance: `XDUT (clk rst vin out metric preamp_mon filt1_mon filt2_mon settle_metric) amplifier_filter_chain`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`, `preamp_mon`, `filt1_mon`, `filt2_mon`, `settle_metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `amplifier_filter_chain.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `amplifier_filter_chain.gain` defaults to `1.8` V/V; valid range: gain > 0; sets pre-filter gain about 0.45 V common mode.
- `amplifier_filter_chain.alpha` defaults to `0.3`; valid range: 0 < alpha <= 1; sets each sampled low-pass update coefficient.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_COMMON_MODE`: exercise and make observable: Initialization or active-high reset returns the preamp and both filter stages near 0.45 V and leaves settle_metric low. Required traces: `time`, `rst`, `out`, `metric`, `preamp_mon`, `filt1_mon`, `filt2_mon`, `settle_metric`.
- `P_BOUNDED_PREAMP`: exercise and make observable: At each rising clock edge, preamp_mon and metric equal gain times the sampled vin deviation about 0.45 V, clamped to 0 V through 0.9 V. Required traces: `time`, `clk`, `vin`, `metric`, `preamp_mon`.
- `P_FIRST_FILTER_STAGE`: exercise and make observable: Filt1_mon applies the sampled first-order alpha update toward the bounded preamp target. Required traces: `time`, `clk`, `preamp_mon`, `filt1_mon`.
- `P_SECOND_FILTER_STAGE`: exercise and make observable: Filt2_mon applies a second sampled alpha update toward the newly updated first-stage value, and out follows filt2_mon. Required traces: `time`, `clk`, `filt1_mon`, `filt2_mon`, `out`.
- `P_CASCADE_LAG`: exercise and make observable: After a large input change, the second-stage output visibly lags the bounded preamp target while the two stage monitors preserve cascade order. Required traces: `time`, `clk`, `vin`, `preamp_mon`, `filt1_mon`, `filt2_mon`, `out`.
- `P_SETTLE_STATUS`: exercise and make observable: Settle_metric is 0.9 V when the output-target error is below 0.16 V and 0.1 V while the chain is recovering. Required traces: `time`, `preamp_mon`, `out`, `settle_metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Implement a composed baseband conditioning block: a bounded gain stage
  followed by two cascaded sampled low-pass states.
- Initialize the pre-filter target, both filter states, `out`, `metric`,
  `preamp_mon`, `filt1_mon`, and `filt2_mon` near `0.45 V`; initialize
  `settle_metric` low.
- On each rising `clk` crossing, update the chain. While `rst` is active high,
  reset the chain to the initial common-mode state.
- When reset is low, form a pre-filter target by amplifying `vin` around
  `0.45 V` as `target = gain * (vin - 0.45) + 0.45`, then clamp the target to
  `[0 V, 0.9 V]`.
- Drive `metric` and `preamp_mon` exactly from the bounded pre-filter target.
- Update the first sampled low-pass state as `s1_next = s1 + alpha * (target - s1)`.
- Update the second sampled low-pass state after the first update as
  `s2_next = s2 + alpha * (s1_next - s2)`.
- Drive `filt1_mon` and `filt2_mon` from those two cascaded low-pass states.
- Drive `out` from the second filtered state so it visibly lags the pre-filter
  target during large input changes.
- Drive `settle_metric` as a voltage-coded settled-status output: high when
  `abs(out - target) < 0.16 V` and low while the chain is still recovering.
  Use 0.9 V for the settled level and 0.1 V for the recovering level.

The visible testbench is a public verification scenario for wiring and saved
observables. Do not hard-code its transient stop time, waveform breakpoints, or
sample windows into the DUT.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`, `preamp_mon`, `filt1_mon`, `filt2_mon`, `settle_metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
