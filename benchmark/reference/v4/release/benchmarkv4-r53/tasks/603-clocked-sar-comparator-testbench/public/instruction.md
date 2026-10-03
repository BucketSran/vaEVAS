# Clocked SAR Comparator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked SAR Comparator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `clocked_sar_comparator.va`:
  - Module `clocked_sar_comparator` (entry)
    - position 0: `CMPCK` (input, electrical)
    - position 1: `VINN` (input, electrical)
    - position 2: `VINP` (input, electrical)
    - position 3: `DCMPN` (output, electrical)
    - position 4: `DCMPP` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/clocked_sar_comparator.va`
- DUT instance: `XDUT (cmpck vinn vinp dcmpn dcmpp) clocked_sar_comparator`
- Required saved public traces: `cmpck`, `vinn`, `vinp`, `dcmpn`, `dcmpp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `clocked_sar_comparator.vdd` defaults to `0.9` V; valid range: vdd > 0; sets the logic-high level and twice the CMPCK crossing threshold.
- `clocked_sar_comparator.td_cmp` defaults to `2e-11` s; valid range: td_cmp >= 0; sets output delay after clock events.
- `clocked_sar_comparator.tr` defaults to `5e-12` s; valid range: tr >= 0; sets decision-output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_PRECHARGE`: exercise and make observable: Both decision outputs initialize high at vdd. Required traces: `time`, `dcmpn`, `dcmpp`.
- `P_FALLING_EDGE_PRECHARGE`: exercise and make observable: Each falling CMPCK crossing through vdd/2 resets both DCMPN and DCMPP high. Required traces: `time`, `cmpck`, `dcmpn`, `dcmpp`.
- `P_POSITIVE_DIFFERENTIAL_DECISION`: exercise and make observable: On a rising CMPCK crossing with VINP greater than VINN, DCMPP is high and DCMPN is low. Required traces: `time`, `cmpck`, `vinp`, `vinn`, `dcmpn`, `dcmpp`.
- `P_NEGATIVE_DIFFERENTIAL_DECISION`: exercise and make observable: On a rising CMPCK crossing with VINP less than VINN, DCMPN is high and DCMPP is low. Required traces: `time`, `cmpck`, `vinp`, `vinn`, `dcmpn`, `dcmpp`.
- `P_EQUAL_INPUT_DECISION`: exercise and make observable: On a rising CMPCK crossing with equal differential inputs, both decision outputs become low. Required traces: `time`, `cmpck`, `vinp`, `vinn`, `dcmpn`, `dcmpp`.
- `P_LATCHED_HOLD_AND_TIMING`: exercise and make observable: The precharged or decided state holds between clock events and output changes use td_cmp delay and tr smoothing. Required traces: `time`, `cmpck`, `dcmpn`, `dcmpp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize both decision outputs high.
- Whenever `CMPCK` falls through `vdd/2`, precharge/reset both decision outputs
  high.
- Whenever `CMPCK` rises through `vdd/2`, latch a differential decision:
  `DCMPP` goes high when `VINP > VINN`, `DCMPN` goes high when `VINP < VINN`,
  and both outputs go low for an equal-input decision.
- Hold the latched or precharged state until the next clock event.
- Drive outputs as smooth voltage-domain levels using the configured delay and
  transition time.


The required trace names are: `time`, `cmpck`, `vinn`, `vinp`, `dcmpn`, `dcmpp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
