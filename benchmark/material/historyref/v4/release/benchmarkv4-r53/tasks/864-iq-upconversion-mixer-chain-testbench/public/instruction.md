# I/Q Upconversion Mixer Chain Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `I/Q Upconversion Mixer Chain` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `iq_upconversion_mixer.va`:
  - Module `iq_upconversion_mixer` (entry)
    - position 0: `i_in` (input, electrical)
    - position 1: `q_in` (input, electrical)
    - position 2: `lo_i` (input, electrical)
    - position 3: `lo_q` (input, electrical)
    - position 4: `rst` (input, electrical)
    - position 5: `enable` (input, electrical)
    - position 6: `rf_out` (output, electrical)
    - position 7: `i_mix_dbg` (output, electrical)
    - position 8: `q_mix_dbg` (output, electrical)
    - position 9: `quad_ok` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/iq_upconversion_mixer.va`
- DUT instance: `XDUT (i_in q_in lo_i lo_q rst enable rf_out i_mix_dbg q_mix_dbg quad_ok) iq_upconversion_mixer`
- Required saved public traces: `i_in`, `q_in`, `lo_i`, `lo_q`, `rst`, `enable`, `rf_out`, `i_mix_dbg`, `q_mix_dbg`, `quad_ok`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `iq_upconversion_mixer.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module iq_upconversion_mixer.
- `iq_upconversion_mixer.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module iq_upconversion_mixer.
- `iq_upconversion_mixer.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module iq_upconversion_mixer.
- `iq_upconversion_mixer.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module iq_upconversion_mixer.
- `iq_upconversion_mixer.gain` defaults to `1.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public gain behavior for module iq_upconversion_mixer.
- `iq_upconversion_mixer.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module iq_upconversion_mixer.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or disabled operation drives RF and debug outputs to vcm and clears quad_ok. Required traces: `time`, `rst`, `enable`, `rf_out`, `i_mix_dbg`, `q_mix_dbg`, `quad_ok`.
- `P_IQ_SIGNED_MIXING`: exercise and make observable: I and Q debug outputs equal vcm plus the specified signed LO products, including the negative Q-path convention. Required traces: `time`, `i_in`, `q_in`, `lo_i`, `lo_q`, `i_mix_dbg`, `q_mix_dbg`.
- `P_RF_SUM_CLAMP`: exercise and make observable: rf_out equals the bounded sum of the I and Q path contributions about vcm. Required traces: `time`, `i_in`, `q_in`, `lo_i`, `lo_q`, `rf_out`, `i_mix_dbg`, `q_mix_dbg`.
- `P_QUADRATURE_ACTIVITY`: exercise and make observable: quad_ok asserts only after each LO input has crossed threshold since the latest reset or enable event. Required traces: `time`, `lo_i`, `lo_q`, `rst`, `enable`, `quad_ok`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, drive `rf_out`, `i_mix_dbg`, and `q_mix_dbg` to `vcm` and clear `quad_ok`.
- Interpret `lo_i` and `lo_q` as quadrature LO phases and assert `quad_ok` when both phases are toggling.
- Interpret each LO as +1 above `vth` and -1 otherwise. Define the I-path contribution as `gain * (V(i_in) - vcm) * lo_i_sign` and the Q-path contribution as `-gain * (V(q_in) - vcm) * lo_q_sign`.
- Drive `i_mix_dbg` and `q_mix_dbg` to `vcm` plus their respective signed path contribution.
- Drive `rf_out` to `vcm` plus the sum of the two path contributions, bounded to `vss..vdd`.
- Assert `quad_ok` only after both LO inputs have exhibited at least one threshold crossing since the latest reset or enable. When either LO phase is missing, hold `quad_ok` low and keep the RF output bounded around `vcm`.


The required trace names are: `time`, `i_in`, `q_in`, `lo_i`, `lo_q`, `rst`, `enable`, `rf_out`, `i_mix_dbg`, `q_mix_dbg`, `quad_ok`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
