# Lock Detector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Lock Detector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `lock_detector.va`:
  - Module `lock_detector` (entry)
    - position 0: `ref_clk` (input, electrical)
    - position 1: `fb_clk` (input, electrical)
    - position 2: `rst_n` (input, electrical)
    - position 3: `lock` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/lock_detector.va`
- DUT instance: `XDUT (ref_clk fb_clk rst_n lock) lock_detector`
- Required saved public traces: `ref_clk`, `fb_clk`, `rst_n`, `lock`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `lock_detector.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets input logic thresholds.
- `lock_detector.vdd` defaults to `0.9` V; valid range: vdd > 0; sets lock high level.
- `lock_detector.tol` defaults to `2e-09` s; valid range: tol >= 0; sets maximum ref-to-feedback edge separation.
- `lock_detector.need` defaults to `3`; valid range: need >= 1; sets consecutive aligned reference events required for lock.
- `lock_detector.tr` defaults to `5e-10` s; valid range: tr > 0; sets lock transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ALIGNMENT_STREAK`: exercise and make observable: lock asserts only after need consecutive reference edges whose most recent feedback edge is within tol. Required traces: `time`, `ref_clk`, `fb_clk`, `rst_n`, `lock`.
- `P_PREMATURE_LOCK`: exercise and make observable: lock remains low before the need-th consecutive aligned reference event. Required traces: `time`, `ref_clk`, `fb_clk`, `lock`.
- `P_MISS_BREAKS_STREAK`: exercise and make observable: A reference event outside tol breaks the streak and clears lock. Required traces: `time`, `ref_clk`, `fb_clk`, `lock`.
- `P_RESET_REACQUIRE`: exercise and make observable: Active-low reset clears stored edge history, streak, and lock and requires a fresh post-reset acquisition. Required traces: `time`, `ref_clk`, `fb_clk`, `rst_n`, `lock`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `rst_n` is active low. While reset is low, clear the consecutive-hit counter and drive `lock` low.
- On every rising edge of `fb_clk`, record that feedback edge time.
- Feedback edges observed while `rst_n` is low must not count toward a later post-reset lock sequence.
- On every rising edge of `ref_clk` while reset is high, compare the reference edge time with the most recent feedback rising edge time.
- A reference event is aligned only when the most recent feedback rising edge is within `tol` of that reference rising edge.
- Assert `lock` only after `need` consecutive aligned reference events.
- Before the `need`th consecutive aligned reference event, `lock` must remain low.
- Any reference event whose most recent feedback edge is outside the `tol` window breaks the streak and drives `lock` low.
- A later active-low reset must clear an already asserted lock and require `need` new consecutive aligned reference events before reassertion.

Use voltage contributions for `lock`, preferably with `transition(...)`. Do not use current contributions, `ddt()`, or `idt()`.


The required trace names are: `time`, `ref_clk`, `fb_clk`, `rst_n`, `lock`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
