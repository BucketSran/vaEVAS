# Aperture-delay track-and-hold

Build a voltage-domain Verilog-A track-and-hold in which each rising clock crossing schedules a sample at a later aperture instant. The model must read the input at that instant, not at the clock edge, and then hold the value.

## Spec

Use the module and port order declared in `/app/circuit.va`. The module is `aperture_sample_hold`. Its electrical ports are `VDD`, `VSS`, `clk`, `vin`, and `vout`, in that order. `clk` is the voltage-coded sampling clock, `vin` is the analog input, and `vout` is the held analog output. `VDD` and `VSS` are supply connections. Every voltage in this contract is measured relative to ground (node 0).

Declare three overrideable real parameters:

- `vth`: clock threshold in volts, default 0.45.
- `taperture`: aperture delay in seconds, default 200 ps. Legal values are greater than 0.
- `tedge`: maximum output transition time in seconds, default 50 ps. Legal values are greater than 0.

A trigger is a rising crossing of `V(clk)` through `vth` after time 0. A trigger at time `t_k` schedules exactly one capture at the aperture instant `c_k = t_k + taperture`. At `c_k`, the model reads the instantaneous value of `vin` and makes it the held value. The value of `vin` at the trigger is not used. Falling crossings, the level of `clk` at `c_k`, and a `clk` level above `vth` at time 0 do not start or cancel a capture. The model has no reset or enable.

The held value starts as the value of `vin` at time 0. Before the first capture, `vout` equals that initial value even when `vin` changes. Between captures, `vout` keeps the latest held value and does not follow `vin`.

When a capture changes the held value, `vout` does not move before `c_k`. It then moves monotonically from its value at `c_k` to the new held value and reaches it no later than `c_k + tedge`. The transition may be faster than `tedge`. If the next capture occurs before that transition has finished, `vout` turns toward the newer held value in the same way.

`VDD` and `VSS` do not affect the model. `vout` reproduces held values outside the interval from `VSS` to `VDD`. It does not clamp, shift, or scale the held value, including while either supply changes.

Legal stimuli: `vin` is continuous and stays between -1 V and 2 V. `VDD` and `VSS` are arbitrary continuous voltages. `clk` starts at a level different from `vth` and never rests at `vth`. When `clk` reaches `vth`, it always crosses it; it never touches `vth` and returns to the same side. Between two successive crossings of `vth`, `clk` moves at least 50 mV away from `vth`. Each trigger occurs more than `taperture` after the previous trigger, so no capture is pending when a trigger arrives and no trigger coincides with the previous aperture instant.

Acceptance uses `epsilon_v = 2 mV`, a capture-time tolerance `tau_s = 2 ps`, and an output-timing tolerance `tau_t = 5 ps`. Trigger times are the rising `vth` crossings of the observed `clk`. For capture `k`, the accepted held range `[lo_k, hi_k]` is the range of `vin` over `[c_k - tau_s, c_k + tau_s]`. For the initial value, the accepted range is the single value of `vin` at time 0.

- Hold: in each hold interval, a single value `h` in the accepted range must lie within `epsilon_v` of every observed `vout` sample. The initial hold interval runs from time 0 to `c_1 - tau_t`, or to the end of the run, and always contains time 0, even when `c_1` is earlier than `tau_t`. The hold interval of capture `k` runs from `c_k + tedge + tau_t` to `c_(k+1) - tau_t`, or to the end of the run. A hold interval of a capture that the next capture leaves empty is not checked.
- Transition: from `c_k - tau_t` until the hold interval of capture `k` begins, or until `c_(k+1) - tau_t` if that comes first, `vout` stays within `epsilon_v` of the smallest interval that contains the accepted range being left and the new accepted range. When a transition was cut short by the next capture, the range being left covers every held value since the last completed hold. From `c_k + tau_t` to the end of that window, `vout` does not reverse direction by more than `epsilon_v`, and it moves toward the new accepted range: if every `vout` sample from `c_k - tau_t` to `c_k + tau_t` is more than `epsilon_v` above `hi_k`, `vout` does not rise by more than `epsilon_v` in that part of the window, and if every such sample is more than `epsilon_v` below `lo_k`, `vout` does not fall by more than `epsilon_v`.

The observation grid is 2 ps. Final evaluation reruns the public case and adds other inputs and parameter values inside this contract, including conditions that are not in the public case. Every required check must pass. An executed attempt that fails scores 0, and the cause is recorded separately. A missing simulator, or any other execution or infrastructure failure, is not evidence that the model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `aperture_sample_hold` on the supplied module and port declarations, including the three parameters.
- Deliver the external trigger, capture, hold, and output behavior in Spec. Any implementation that meets this interface and external behavior is acceptable. A particular state variable, event function, or output operator is not required.
- The submitted model must not read files, start processes, or depend on the times or values of a particular stimulus. This restriction applies to the submitted model. You may read the public materials and run the public check.

Run `python3 /app/testbench/check.py` for the public representative case. The [public testbench guide](testbench/README.md) documents the Spectre dependency, the observation method, timeouts, outputs, and exit codes.

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
