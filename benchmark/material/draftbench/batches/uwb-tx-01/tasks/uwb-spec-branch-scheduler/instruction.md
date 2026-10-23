# Implement the supply scheduler for the eight RF oscillator branches of an IR-UWB transmitter

The transmitter has eight RF ring-oscillator branches, one per carrier frequency. A pulse generator sends every symbol on one of two command lanes, a and b, as a precharge request followed by an RF window. Build the scheduler between the pulse generator and the branches. It powers, precharges, releases, holds and turns off the branches with at most two powered at a time, gates each lane's window when its branch is ready, and reports dropped symbols.

## Spec

Use the module name and port order of the starter. All ports are voltages relative to ground. Implement these parameters:

| Parameter | Meaning | Default | Allowed range |
| --- | --- | --- | --- |
| `n_pre` | integer: request lead of the pulse generator, in grid steps (S5, S9) | 2 | 1 to 15 |
| `delta0` | grid step of the pulse generator, s | 93.00595238095238e-12 | 60e-12 to 150e-12 |
| `t_tail` | duration of TAIL, s | 150e-12 | 20e-12 to 600e-12 |
| `t_hold` | hold time, s (S5) | 200e-12 | 0 to 3e-9 |
| `t_conf` | width of a conflict pulse, s | 200e-12 | 50e-12 to 800e-12 |
| `vdd` | high level of `pwr`, `pre`, `rel`, `gate_a`, `gate_b` and `conflict`, V | 1.0 | 0.5 to 1.8 |
| `vth` | input threshold, V | 0.5 | 0.2 to 1.5 |
| `tr` | duration of every output edge, s | 2e-12 | 1e-12 to 5e-12 |

S1. Requests and windows. An input is high when its voltage is greater than `vth`. Lane x (a or b) has the inputs `pre_x`, `rf_x` and `sel_x[2:0]`. A request on lane x is a rising crossing of `pre_x` through `vth` while `rst` is low. `sel_x[2:0]` is read at that instant and gives the requested branch k (bit 0 is the least significant bit). The window of the request starts at the next rising crossing of `rf_x` and ends at the falling crossing of `rf_x` that follows.

S2. Branch states and outputs. Each branch k = 0 to 7 is in one of these states: OFF (state number 0), PRECHARGE (1), ACTIVE (3), TAIL (4) or HOLD (5). State number 2 (release settling) has zero length in this task and never appears. A branch is powered in every state except OFF. The outputs of branch k are:

| State | `pwr[k]` | `pre[k]` | `rel[k]` |
| --- | --- | --- | --- |
| OFF | 0 | 0 | 0 |
| PRECHARGE | `vdd` | `vdd` | 0 |
| ACTIVE, TAIL, HOLD | `vdd` | 0 | `vdd` |

`st[k]` is 0.2 V times the state number of branch k. `nsup` is 1 V times the number of powered branches. `st` and `nsup` do not scale with `vdd`. At the start of the simulation every branch is OFF, and `gate_a`, `gate_b` and `conflict` are low.

S3. Grants. A request for branch k is handled by the first rule that applies:

- (a) Warm grant: k is powered. The request is granted. k keeps its state and continues to precharge or oscillate. No other branch changes.
- (b) Cold grant: k is OFF and fewer than two branches are powered. The request is granted and k enters PRECHARGE.
- (c) Take-over: k is OFF, two branches are powered, and one of them is in idle HOLD (S5). That branch turns OFF and k enters PRECHARGE at the same instant. The request is granted.
- (d) Drop: in all other cases the request is not granted. No branch changes, and `conflict` pulses (S6).

A granted request is waiting from the request until its window starts. At most two branches are powered at any time.

S4. Windows and gates. When the window of a granted request for branch k starts, k enters ACTIVE and `gate_x` rises. From PRECHARGE this is the release. From TAIL or HOLD the branch keeps oscillating. When the window ends, `gate_x` falls. k then enters TAIL, unless another granted window on k is still open. If a window of the other lane on k starts when this window ends (both `rf` edges centred on the same instant, their crossings less than 1 ps apart), k stays ACTIVE without a TAIL. Some windows belong to a request that was dropped, cancelled by a reset or made while `rst` was high. Such a window changes nothing and gives no gate.

S5. Tail and hold. A branch stays in TAIL for `t_tail` and then enters HOLD, unless a window starts on it first (S4). A branch in HOLD keeps oscillating.

- If the branch has a waiting granted request when it enters HOLD, it stays in HOLD until that window starts.
- Otherwise it is in idle HOLD. It turns OFF after t_wait = max(0, `t_hold` − `n_pre`·`delta0`), unless a request for it arrives first. Such a request is a warm grant (S3 a), and the branch then stays in HOLD until the window starts.
- If t_wait = 0, a branch without a waiting request goes from TAIL directly to OFF, so `st` falls from 0.8 V to 0.

Each request comes `n_pre`·`delta0` before its window (S9). The result is that a branch keeps oscillating up to its next window when the window starts within max(`t_hold`, `n_pre`·`delta0`) after the end of the TAIL.

S6. Conflict. `conflict` rises at each dropped request and falls `t_conf` after the most recent dropped request.

S7. Reset. `rst` acts asynchronously. At its rising crossing every branch turns OFF and a high `gate_a` or `gate_b` falls. Every granted request is cancelled, whether it is waiting or its window is open. Requests made while `rst` is high are ignored. After `rst` falls, the scheduler starts again with every branch OFF. `rst` may start high.

S8. Output edges. Every change of an output is a linear edge of duration `tr`. The edge starts, without delay, at the event that causes the change. That event is an input crossing (S1, S4, S7) or the end of a TAIL, an idle HOLD or a conflict pulse. These ends are exactly `t_tail`, t_wait and `t_conf` after the event that started them. For an output that switches between 0 and `vdd`, the `vdd`/2 crossing therefore lies `tr`/2 after the event. Changes of one output at the same instant give one edge to the final value. An output whose value does not change has no edge.

S9. Operating domain.

- Inputs switch between 0 V and a level VIN, where `vth` + 0.3 V <= VIN <= 1.8 V, with linear edges no longer than 10 ps. `rst` may start high.
- The lanes come from a pulse generator that uses the same `n_pre` and `delta0` as the scheduler. Consecutive symbols alternate between lane a and lane b. Each window starts `n_pre`·`delta0` after its request (`pre_x` falls as `rf_x` rises) and lasts 9·`delta0`. Windows start on a `delta0` grid, at least 9·`delta0` apart, so windows of the two lanes can touch but never overlap. The next request on a lane comes after the previous window of that lane has ended. `sel_x` changes only while lane x has no pending request, at least 20 ps before the next request.
- Each end of a TAIL or idle HOLD lies at least 10 ps from every other event: requests, window edges, `rst` crossings and other such ends. No request comes within 10 ps of the end of a conflict pulse. `rst` crossings are at least 10 ps from lane crossings, and `rst` does not rise during a conflict pulse.
- A take-over never finds two branches in idle HOLD. t_wait is either 0 or at least 10 ps.

S10. Acceptance.

- `pwr`, `pre`, `rel`, `gate_a`, `gate_b` and `conflict`: the observed `vdd`/2 crossings are compared one to one, in order, with the crossings that S1 to S8 give. The counts must be equal, the directions must match, and each crossing must be within 2 ps of its expected time.
- `st[k]` is observed at 0.1, 0.3, 0.5, 0.7, 0.9 and 1.1 V, and `nsup` at 0.5, 0.9, 1.1, 1.5, 1.9 and 2.1 V. These thresholds lie 0.1 V on either side of every level. For each threshold the counts and directions of the crossings must match the expected waveform, so every level must be within 0.1 V of its value. For every expected edge, the crossing of the threshold nearest the middle of that edge must be within 2 ps of its expected time; on a tie the earlier threshold is used. The other crossings lie nearer the start or end of the edge and are compared only in count and direction.
- The observed number of high `pwr` outputs must never exceed two.

Final evaluation reruns the public cases and adds other cases inside S9:

- `n_pre` = 1 with requests inside the idle-hold window;
- take-overs with a long `t_hold`;
- long random symbol sequences with empty frames;
- drops on a different `delta0` grid;
- resets in different phases of activity;
- nondefault values of every parameter, with two instances that have different parameters and are driven by the same lanes.

Every check of every instance must pass for task score 1. An executed attempt that fails any check scores 0, and its cause is recorded separately. A run that the simulator cannot execute has no score and is reported as an execution problem.

## Deliverable

- Edit `/app/circuit.va`. Keep the supplied module name and port declarations, declare the eight parameters with the names, types and defaults above, and implement the behavior.
- Any Verilog-A implementation that meets the interface and the external behavior is acceptable. The internal state variables, the bookkeeping of powered branches and the event organization are your choice.
- The submitted model must be self-contained apart from the standard Verilog-A headers. It must not read or write files or start external processes.

Run `python3 /app/testbench/check.py run` to simulate the public cases and print each check with its limit, measured value and PASS/FAIL. `python3 /app/testbench/check.py plan` lists the cases without simulating. The [public testbench guide](/app/testbench/README.md) explains the cases, the lane stimulus, the simulator and the output files.

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
