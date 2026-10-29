# Repair the UVLO reset chain

Repair the supplied undervoltage, reset-release, enable, and stateful downstream chain. The fixed backend is Spectre. The starter is the complete erroneous engineering input. This is an original behavioral power-control task. It does not claim equivalence to a transistor POR.

## Spec

The top module is `power_chain(vin, clk, pgood, resetb, enable, activity)`. `vin` and `clk` are inputs. `pgood`, `resetb`, `enable`, and `activity` are outputs. The chain has four responsible parts, and each responsibility must remain observable:

- `chain_uvlo(vin, pgood)` monitors the supply with hysteresis.
- `chain_release(pgood, resetb)` releases reset only after continuous qualification.
- `chain_enable(pgood, resetb, enable)` is the enable gate.
- `chain_downstream(clk, resetb, enable, activity)` is the clocked stateful consumer.

`vin` rising through 0.65 V asserts `pgood`. `vin` falling through 0.55 V withdraws `pgood`. Inside the hysteresis band, `pgood` holds. The supplied real defaults are `high=0.65`, `low=0.55`, and `tr=10 ps` on the monitor. The public parameter window remains 0.64 V to 0.66 V for the upper threshold and 0.54 V to 0.56 V for the lower threshold.

`resetb` releases after `pgood` has stayed high for 10 ns. The supplied release defaults are `delay=10 ns` and `tr=10 ps`. The public window for that delay is 9.9 ns to 10.1 ns. Any loss of `pgood` asserts reset immediately and cancels the old timer. The next valid interval must accumulate a new full 10 ns. The 10 ns qualification allows 0.15 ns of propagation tolerance.

`enable` is high only when `pgood` and `resetb` are both valid. `activity` starts at 0. While `enable` and `resetb` are both valid, each rising `clk` edge adds 0.1 V. Otherwise `activity` clears. Withdrawing protection also clears it. Under a normal supply the downstream activity must increment. The downstream transition default is `tr=10 ps`.

Logic high is 0.9 V. The logic threshold is 0.45 V. Propagation and smoothing must complete within 0.15 ns. Changing parameters inside the public windows must still meet this external contract. Conditions that forbid an action must still meet the on-time startup requirement. The supply and clock stimuli used for acceptance stay fixed.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit these five supplied files. Each already contains the complete erroneous source, and all five are collected:
  - `/app/circuit.va`, the `power_chain` top connections, formerly named `dut.va`
  - `/app/uvlo.va`, module `chain_uvlo`
  - `/app/release.va`, module `chain_release`
  - `/app/enable.va`, module `chain_enable`
  - `/app/downstream.va`, module `chain_downstream`
- You may change the top connections, the four modules, and their design parameters, or rebuild the system inside these files. Keep the public module names, ports, and external behavior. The editable set is not smaller than those five files. New files outside this set are not collected.
- Any implementation that keeps the four responsibilities and the external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not edit the public development bench. The submitted model must not run an external program or read hidden final-evaluation material. This restriction applies to the submitted model. You may build diagnostic stimuli and run the public check.

Run `python3 /app/testbench/check.py --output /app/output/public-check`. The [public testbench guide](/app/testbench/README.md) documents the Spectre dependency, case selection, timeouts, output layout, and diagnostic exit codes. Public feedback is not the final task score.

This is an implementation task, not a repository-audit task.
Work in /app and modify only the declared deliverables; do not edit public development benches, model libraries, or external fixtures.
Make one bounded inspection pass over this instruction, the declared deliverables, supplied starter material, and public development benches.
As the task solver, create a runnable candidate in every file named in the Deliverable section before beginning detailed exploration, and keep those files updated as you work.
If your working time expires, the evaluator copies those files exactly as they exist at that moment and runs the verifier on them.
If any declared file is missing or empty, the result is zero reward.
Temporary files are not submitted.

If a concrete model, tool, or execution problem appears, investigate it as needed before continuing.
Iterate by editing the declared deliverables and using public development benches to diagnose observed behavior.
Do not repeatedly enumerate files, reread unchanged references, or retry unchanged discovery commands instead of editing and simulating.
