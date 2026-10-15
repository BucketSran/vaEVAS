# Hysteresis Comparator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Hysteresis Comparator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cmp_hysteresis.va`:
  - Module `cmp_hysteresis` (entry)
    - position 0: `VINN` (input, electrical)
    - position 1: `VINP` (input, electrical)
    - position 2: `OUTN` (output, electrical)
    - position 3: `OUTP` (output, electrical)
    - position 4: `VSS` (input, electrical)
    - position 5: `VDD` (input, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/cmp_hysteresis.va`
- DUT instance: `XFB_DUT (vinn vinp out_n out_p vss vdd) cmp_hysteresis tedge=50p vhys=10m`
- Required saved public traces: `vinn`, `vinp`, `out_n`, `out_p`, `vss`, `vdd`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cmp_hysteresis.vhys` defaults to `0.01` V; valid range: vhys >= 0; sets total differential hysteresis width centered at zero.
- `cmp_hysteresis.tedge` defaults to `5e-11` s; valid range: tedge > 0; sets complementary output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_DECISION`: exercise and make observable: OUTP initializes high only when the initial differential exceeds positive vhys over two; otherwise OUTP initializes low and OUTN high. Required traces: `time`, `vinp`, `vinn`, `out_p`, `out_n`.
- `P_POSITIVE_SWITCH_THRESHOLD`: exercise and make observable: The low OUTP state switches high only on a rising differential crossing of positive vhys over two. Required traces: `time`, `vinp`, `vinn`, `out_p`, `out_n`.
- `P_NEGATIVE_SWITCH_THRESHOLD`: exercise and make observable: The high OUTP state switches low only on a falling differential crossing of negative vhys over two. Required traces: `time`, `vinp`, `vinn`, `out_p`, `out_n`.
- `P_HYSTERESIS_HOLD`: exercise and make observable: The previous decision is retained while the differential remains inside the hysteresis band. Required traces: `time`, `vinp`, `vinn`, `out_p`, `out_n`.
- `P_COMPLEMENTARY_RAIL_OUTPUT`: exercise and make observable: OUTP and OUTN remain complementary and use the local VDD and VSS rail levels after smoothing. Required traces: `time`, `out_p`, `out_n`, `vdd`, `vss`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize `OUTP` high only when `V(VINP,VSS) - V(VINN,VSS)` is above
  `+vhys/2`; otherwise initialize `OUTP` low and `OUTN` high.
- Switch to the high `OUTP` state only when the differential input rises
  through `+vhys/2`.
- Switch back to the low `OUTP` state only when the differential input falls
  through `-vhys/2`.
- Hold the previous decision while the differential input remains inside the
  hysteresis band.
- Drive `OUTP` and `OUTN` as complementary rail-referenced outputs using finite
  transition-style smoothing.


The required trace names are: `time`, `vinn`, `vinp`, `out_n`, `out_p`, `vss`, `vdd`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
