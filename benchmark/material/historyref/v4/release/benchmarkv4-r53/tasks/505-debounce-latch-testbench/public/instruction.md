# Debounce Latch Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Debounce Latch` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `debounce_latch.va`:
  - Module `debounce_latch` (entry)
    - position 0: `sig` (input, electrical)
    - position 1: `rst_n` (input, electrical)
    - position 2: `out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/debounce_latch.va`
- DUT instance: `XDUT (sig rst_n out) debounce_latch`
- Required saved public traces: `sig`, `rst_n`, `out`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `debounce_latch.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets sig and rst_n decision threshold.
- `debounce_latch.vdd` defaults to `0.9` V; valid range: vdd > 0; sets output high level.
- `debounce_latch.stable` defaults to `1.2e-08` s; valid range: stable >= 0; sets rising-decision qualification duration.
- `debounce_latch.tr` defaults to `5e-10` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ACTIVE_LOW_RESET`: exercise and make observable: out is low and pending qualification is cancelled whenever rst_n is below vth. Required traces: `time`, `rst_n`, `out`.
- `P_RISE_QUALIFICATION`: exercise and make observable: A sig rising edge sets out high only after sig and rst_n remain high for stable seconds. Required traces: `time`, `sig`, `rst_n`, `out`.
- `P_FALL_CLEAR`: exercise and make observable: A sig falling edge clears out and cancels pending qualification. Required traces: `time`, `sig`, `out`.
- `P_EVENT_HOLD`: exercise and make observable: out holds between reset, sig-edge, and qualification-timer events. Required traces: `time`, `sig`, `rst_n`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize `out` low.
- When `rst_n` is below `vth`, force `out` low and cancel any pending
  qualification.
- When `sig` rises through `vth` while reset is released, start a qualification
  timer.
- When the qualification timer expires, set `out` high only if both `sig` and
  `rst_n` are still above `vth`.
- When `sig` falls below `vth`, clear `out` low and cancel any pending
  qualification.
- Hold the debounced output state between reset, input-edge, and timer events.


The required trace names are: `time`, `sig`, `rst_n`, `out`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
