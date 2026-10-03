# Comparator Delay Overdrive Meter Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Comparator Delay Overdrive Meter` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `comparator_delay_overdrive_meter.va`:
  - Module `comparator_delay_overdrive_meter` (entry)
    - position 0: `vdd` (input, electrical)
    - position 1: `vss` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `vinp` (input, electrical)
    - position 4: `vinn` (input, electrical)
    - position 5: `outp` (input, electrical)
    - position 6: `outn` (input, electrical)
    - position 7: `delay_ps` (output, electrical)
    - position 8: `overdrive_mv` (output, electrical)
    - position 9: `polarity` (output, electrical)
    - position 10: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/comparator_delay_overdrive_meter.va`
- DUT instance: `XMEAS (vdd vss clk vinp vinn outp outn delay_ps overdrive_mv polarity valid) comparator_delay_overdrive_meter`
- Required saved public traces: `clk`, `vinp`, `vinn`, `outp`, `outn`, `delay_ps`, `overdrive_mv`, `polarity`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `comparator_delay_overdrive_meter.tr` defaults to `20p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CLOCK_ARMED_MEASUREMENT`: exercise and make observable: Each rising `clk` threshold crossing stores the launch time, captures absolute differential overdrive, and arms exactly one pending measurement. Required traces: `time`, `clk`, `vinp`, `vinn`, `overdrive_mv`, `valid`.
- `P_DECISION_DELAY_CAPTURE`: exercise and make observable: The first qualifying `outp` or `outn` decision edge while armed reports the elapsed clock-to-decision delay in `delay_ps`. Required traces: `time`, `clk`, `outp`, `outn`, `delay_ps`, `valid`.
- `P_ABSOLUTE_OVERDRIVE_METRIC`: exercise and make observable: `overdrive_mv` reports the absolute input differential magnitude at launch time. Required traces: `time`, `clk`, `vinp`, `vinn`, `overdrive_mv`.
- `P_POLARITY_AND_VALID_FLAG`: exercise and make observable: `polarity` reports the winning output decision direction and `valid` asserts only for a completed armed measurement. Required traces: `time`, `outp`, `outn`, `polarity`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising `clk` threshold crossing, store the current time and the absolute differential input overdrive. Arm one pending measurement. When either `outp` or `outn` rises through the decision threshold while armed, drive the voltage on `delay_ps` to the elapsed clock-to-output delay expressed in seconds and drive the voltage on `overdrive_mv` to the stored overdrive expressed in volts. The historical port suffixes name the human-facing diagnostic units; the evaluator converts these SI-valued electrical observables to picoseconds and millivolts. Set `polarity` high for an `outp` decision and low for an `outn` decision, assert `valid`, and disarm until the next clock edge. Hold reported values between measurements.


The required trace names are: `time`, `clk`, `vinp`, `vinn`, `outp`, `outn`, `delay_ps`, `overdrive_mv`, `polarity`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Include the supplied read-only support files only from
  `./dut/support/...`; do not reference `./support/...` or undeclared paths.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
