# Sample-and-hold with periodic leakage

Build a voltage-domain sample-and-hold whose held value leaks on a fixed internal update grid. Each rising crossing of `sample` captures `vin`, and at every leak update the held value is multiplied by `decay`. An active-high `rst` clears the held value at once.

## Spec

Use the starter declaration of `leaky_hold`. Every port is electrical. The positional order is `sample`, `rst`, `vin`, `vout`. `sample`, `rst`, and `vin` are inputs. `vout` is the output. Every voltage in this contract is measured relative to ground (node 0).

Declare these overrideable parameters:

- `vth` = 0.45 V. Threshold for `sample` and `rst`. A level above `vth` is high. Legal range 0.1 V to 0.8 V.
- `decay` = 0.985. Factor that one leak update applies to the held value. Legal range 0.5 to 1.
- `leak_period` = 1 ns. Interval between leak updates. Legal range 0.5 ns to 10 ns.
- `tr` = 500 ps. Output transition time. Legal range 10 ps to 1 ns, and at most `leak_period/2`.

Held value. The model keeps one held value `h`. At t = 0, `h` is 0 V, whatever the inputs are. `h` changes only at the leak updates, captures, and resets below, and keeps its value between them.

Leak updates. The leak update instants are `t_k = k*leak_period` for k = 1, 2, 3, and so on, counted from t = 0. The model generates these instants itself. `sample` and `rst` never add, skip, or move one. At each leak update instant, `h` becomes `decay*h`. The update applies whether `sample` is high or low, and it applies to a negative `h` in the same way, so `h` moves toward 0 V from either side. Between two leak updates `h` is constant; it does not decay continuously.

Captures. A capture is a rising crossing of `sample` through `vth` after t = 0 at which `rst` is low. At a capture, `h` becomes the value of `V(vin)` at the crossing. The captured value stays unchanged until the next leak update instant, which applies `decay` to it as to any other held value: a capture does not restart or shift the leak grid. Falling crossings of `sample` and the level of `sample` do not change `h`, so `vout` does not follow `vin` while `sample` is high. A level of `sample` above `vth` at t = 0 is not a capture.

Reset. A rising crossing of `rst` through `vth` sets `h` to 0 V at once, without waiting for a leak update or a capture. While `rst` is high, rising crossings of `sample` are not captures and `h` stays 0 V. The falling crossing of `rst` changes nothing by itself: `h` stays 0 V until the first capture after it, even if `sample` is already high at that falling crossing. If `rst` is above `vth` at t = 0, the model is in reset from t = 0.

Output. `vout` drives `h`. After each instant that changes `h`, `vout` reaches the new value within `tr` and then stays on it until the next change. This also holds when the next change comes before `vout` has reached the previous value. The waveform inside that `tr` interval is not specified.

Legal inputs:

- `sample` and `rst` switch between 0 V and 0.9 V, and each transition between these levels, the time during which the input is more than 1 mV away from both levels, lasts at most 200 ps. They never rest at `vth`, and at t = 0 each is at least 50 mV away from `vth`. An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.
- Successive `vth` crossings of the same input are at least 0.5 ns apart.
- Every rising crossing of `sample` is at least 50 ps away from every leak update instant, so no capture coincides with a leak update.
- Every crossing of `rst` is at least 0.5 ns away from every rising crossing of `sample`.
- `vin` is continuous and stays between -1 V and +1 V. Within 100 ps of every rising crossing of `sample`, `vin` moves by less than 0.25 mV.

The expected `vout` is calculated with the rules above from the recorded inputs. Crossing times and input values are taken by linear interpolation between saved points. Every saved point is scored, except points less than `1.25*tr` after an instant at which the expected `h` changes by more than 0.1 mV. A change of 0.1 mV or less opens no such interval. At each scored point the error of `V(vout)` is at most 2 mV. A scored waveform uses a time step no coarser than `tr/4`. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `leaky_hold` on the module and positional ports in the starter, including the parameter defaults above. You may define helper modules in the same file.
- Any Verilog-A implementation that meets that interface and the external behavior in Spec is acceptable. The leak grid, the capture and reset rules, and the leak law define the observable output. They do not require a particular state variable, event operator, or event organization.
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
