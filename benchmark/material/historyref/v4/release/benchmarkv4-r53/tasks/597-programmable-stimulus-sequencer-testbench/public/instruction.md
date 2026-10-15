# Programmable Stimulus Sequencer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Programmable Stimulus Sequencer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `programmable_stimulus_sequencer.va`:
  - Module `programmable_stimulus_sequencer` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `mode` (input, electrical)
    - position 3: `gate` (input, electrical)
    - position 4: `out` (output, electrical)
    - position 5: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/programmable_stimulus_sequencer.va`
- DUT instance: `XDUT (clk rst mode gate out metric) programmable_stimulus_sequencer`
- Required saved public traces: `clk`, `rst`, `mode`, `gate`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `programmable_stimulus_sequencer.tr` defaults to `8e-11` s; valid range: finite real; use tr >= 0 for physical transition smoothing; sets rise and fall smoothing for out and metric without changing segment selection.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_IDLE`: exercise and make observable: When rst is above the 0.45 V control threshold, out is held near 0.45 V and metric is low. Required traces: `time`, `rst`, `out`, `metric`.
- `P_RAMP_MODE`: exercise and make observable: For mode below 0.30 V outside reset, out produces a monotonic ramp segment from about 0.18 V toward 0.45 V and metric is near 0.20 V. Required traces: `time`, `rst`, `mode`, `out`, `metric`.
- `P_CHIRP_MODE`: exercise and make observable: For mode from 0.30 V through below 0.60 V, out is a sine segment centered near 0.45 V whose instantaneous frequency increases over the segment, with metric near 0.50 V. Required traces: `time`, `rst`, `mode`, `out`, `metric`.
- `P_BURST_GATE`: exercise and make observable: For mode at or above 0.60 V and gate high, out produces a deterministic PRBS-like burst between the low and high stimulus levels. Required traces: `time`, `clk`, `rst`, `mode`, `gate`, `out`.
- `P_BURST_IDLE`: exercise and make observable: In burst mode with gate low, out returns near 0.45 V and metric reports the idle rather than active-burst status. Required traces: `time`, `rst`, `mode`, `gate`, `out`, `metric`.
- `P_CONTROL_DRIVEN_SELECTION`: exercise and make observable: Mode and gate behavior follows the voltage-coded inputs over arbitrary legal control schedules rather than a fixed stimulus timeline. Required traces: `time`, `clk`, `rst`, `mode`, `gate`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Use low level near 0 V, high level near 0.9 V, and a 0.45 V decision threshold
for voltage-coded control signals. When reset is high, drive `out` near 0.45 V
and `metric` low. Otherwise:

- ramp mode, selected when `mode < 0.30 V`, drives a monotonic ramp segment
  from roughly 0.18 V toward 0.45 V and marks `metric` near 0.20 V;
- chirp mode, selected when `0.30 V <= mode < 0.60 V`, drives a sine segment
  centered near 0.45 V whose instantaneous frequency increases over the segment
  and marks `metric` near 0.50 V;
- burst mode, selected when `mode >= 0.60 V`, drives a gated PRBS-like burst
  between low and high stimulus levels while `gate` is high, returns `out` near
  0.45 V while `gate` is low, and marks `metric` near the burst or idle status.

The visible transient deck is a public verification scenario. Additional
validation may use different control schedules, so derive mode and gating
decisions from the voltage-coded inputs rather than from a particular stimulus
file.


The required trace names are: `time`, `clk`, `rst`, `mode`, `gate`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
