# Capacitive SAR feedback DAC

Build a clocked capacitive feedback DAC that samples a 10-bit word and a two-bit calibration code, then drives a complementary differential output.

## Spec

Use the starter declaration of `cdac_cal`. Every port is electrical. The positional order is `VDD`, `VSS`, `CLK`, `D9`, `D8`, `D7`, `D6`, `D5`, `D4`, `D3`, `D2`, `D1`, `D0`, `CAL0`, `CAL1`, `VDAC_P`, `VDAC_N`.

`VDAC_P` and `VDAC_N` are the complementary differential outputs. `VDD` and `VSS` are supply and reference nodes. `CLK` is the sampling clock. `D9` through `D0` are the main DAC controls, and `CAL0` and `CAL1` are the calibration controls. The interface sentence names the two outputs and does not say whether the supply ports are inputs or inouts. The output equations use `V(VSS)` as the reference for the stated common mode.

Declare these overrideable parameters. No legal range is stated beyond the values and equations here.

- `vcm` = 0.45 V. Output common-mode voltage above `VSS`.
- `swing` = 0.6 V. Differential output swing scale.
- `tt` = 20 ps. Output transition smoothing time.

Use a 0.45 V logic threshold for `CLK`, `D9` through `D0`, `CAL0`, and `CAL1`.

At the initial time, both outputs are `vcm` above `VSS`: `V(VDAC_P) = V(VSS) + vcm` and `V(VDAC_N) = V(VSS) + vcm`.

On each rising `CLK` edge, sample `D9` through `D0`, `CAL0`, and `CAL1`. `D9` is the most significant bit and `D0` is the least significant bit of an unsigned 10-bit word, `code`. `CAL0` contributes one unit and `CAL1` contributes two units of an unsigned calibration code, `cal`. Each calibration unit adds 32 main DAC codes. The effective code is `code + 32*cal`.

The differential voltage is `swing * ((code + 32*cal) / 1023 - 0.5)`. A higher effective code raises `VDAC_P` relative to `VDAC_N`. The two outputs, measured from `VSS`, are `vcm + differential/2` and `vcm - differential/2`. Do not clamp either output.

The outputs hold until the next rising `CLK` edge. Each uses a smooth voltage transition of length `tt`.

Initial levels and edges are unambiguous. `CLK`, `D9` through `D0`, `CAL0`, and `CAL1` never rest at the 0.45 V threshold. Each of them that reaches the threshold always crosses it; it never touches the threshold and returns to the same side. Independent control edges are at least `2*tt` apart. Supplies stay fixed. The logic threshold is the stated 0.45 V. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Each output reaches its new value within `tt` after the rising `CLK` crossing that sets it. Every saved point is scored, for both outputs, except points less than `1.15*tt` after t = 0 or after a rising `CLK` crossing that changes an output target. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `cdac_cal` on the module and positional ports in the starter.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The code equation defines the observable voltages. It does not require a particular state name or event operator.
- The submitted model must not read grading files, replay stored answers, or start external processes. You may read this instruction, the starter, and the public testbench, and you may run the public check. Do not edit the public testbench.

From `/app`, run `python3 testbench/check.py --output /app/output/public-check`.

[testbench/README.md](testbench/README.md) describes that check. The public bench sources stay visible, including [testbench/visible_test.scs](testbench/visible_test.scs). Tool version, timeouts, and diagnostics are in that README.

This is an implementation task, not a repository-audit task.
Work in /app and modify only the declared deliverable; do not edit public development benches, model libraries, or external fixtures.
Make one bounded inspection pass over this instruction, the declared deliverable, supplied starter material, and public development benches.
As the task solver, create a runnable candidate in the file named in the Deliverable section before beginning detailed exploration, and keep that file updated as you work.
If your working time expires, the evaluator copies that file exactly as it exists at that moment and runs the verifier on it.
If the file is missing or empty, the result is zero reward.
Temporary files are not submitted.

If a concrete model, tool, or execution problem appears, investigate it as needed before continuing.
Iterate by editing the declared deliverable and using public development benches to diagnose observed behavior.
Do not repeatedly enumerate files, reread unchanged references, or retry unchanged discovery commands instead of editing and simulating.
