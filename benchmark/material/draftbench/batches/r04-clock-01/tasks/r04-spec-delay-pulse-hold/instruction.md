# Programmable delay cell with pulse hold

Build a voltage-domain Verilog-A programmable delay cell that delays every accepted input pulse as a whole. Both edges of a pulse use the one delay latched when the pulse starts, so loading a new code never changes the width of a pulse that is already accepted. Edges of more than one pulse can be pending at once, and reset discards all of them.

## Spec

Use the module and port order declared in `/app/circuit.va`. The module is `programmable_delay_cell`. Its electrical ports are `in_clk`, `load`, `rst`, `code_5`, `code_4`, `code_3`, `code_2`, `code_1`, `code_0`, and `out_clk`, in that order. `out_clk` is the only output. `code_5` is the most significant code bit and `code_0` the least significant. Every voltage in this contract is measured relative to ground (node 0).

Declare six overrideable real parameters:

- `vth`: input threshold in volts, default 0.45. An input is high above `vth` and low below it.
- `vdd`: high level of `out_clk` in volts, default 0.9.
- `vss`: low level of `out_clk` in volts, default 0.0. Legal values are below `vdd`.
- `delay_min`: delay at code 0 in seconds, default 20 ps. Legal values are greater than 0.
- `delay_lsb`: delay added per code step in seconds, default 3 ps. Legal values are 0 or greater.
- `tr`: maximum output transition time in seconds, default 10 ps. Legal values are greater than 0.

Code loading: a rising crossing of `load` through `vth` while `rst` is low loads the code `32*b5 + 16*b4 + 8*b3 + 4*b2 + 2*b1 + b0`. Here `bi` is 1 when `V(code_i)` is above `vth` at that crossing and 0 otherwise. The code stays until the next load or reset. The level of `load`, its falling crossings, and code-bit changes at other times have no effect. The cell is unloaded at time 0 and after every reset, until the next load.

Pulses: a rising crossing of `in_clk` at `t_r` is accepted when `rst` is low and a code is loaded. An accepted pulse latches the delay `d = delay_min + delay_lsb * code` from the code loaded at `t_r`, and its rising output edge is scheduled at `t_r + d`. The next falling crossing of `in_clk`, at `t_f`, schedules the falling output edge at `t_f + d` with the same `d`, so the output pulse is as wide as the input pulse. A load after `t_r`, while the pulse is high or while its output edges are still pending, does not change `d` or retime those edges. It applies from the next accepted rising crossing. Rising crossings that are not accepted, and falling crossings that do not end an accepted pulse, do nothing.

Several output edges can be pending at the same time. A pulse shorter than its delay has both of its output edges pending. An input low time shorter than the previous pulse's delay leaves that pulse's falling output edge pending when the next pulse's rising output edge is scheduled.

Reset: `rst` above `vth` is reset. At a rising crossing of `rst`, every pending output edge is cancelled and every accepted pulse ends: none of its remaining output edges occurs, and its later falling input crossing schedules nothing. If `out_clk` is high at that crossing, it falls there. While `rst` is high, no rising crossing of `in_clk` is accepted and `load` crossings are ignored. A level above `vth` at time 0 is not a crossing: an `in_clk` already high does not start a pulse, a `load` already high does not load, and an `rst` already high holds the cell in reset until it falls.

Output: at time 0, `out_clk` is at `vss`. An output edge at time `t_e` is either a scheduled edge or a rising `rst` crossing at which `out_clk` is high. `out_clk` does not leave its old level before `t_e`. It then moves monotonically to the new level, `vdd` for a rising edge and `vss` for a falling edge, and reaches it no later than `t_e + tr`. The transition may be faster than `tr`. Between edges, `out_clk` stays at `vss` or `vdd`. While the cell is unloaded or in reset and no edge is in progress, it is at `vss`.

Legal stimuli: every input is continuous, starts at a level different from `vth`, and passes through `vth` without stopping on it. With `d` the delays defined above:

- Every high time of `in_clk`, from a rising crossing to the next falling crossing, is at least `4*tr`.
- For two consecutive accepted pulses with no reset between them, the second rising output edge comes at least `4*tr` after the first falling output edge, so output pulses never merge or change order.
- An `in_clk` rising crossing never occurs while a rising output edge is pending or within 20 ps after it. A falling crossing likewise never occurs while a falling output edge is pending or within 20 ps after it. So at most one rising and one falling output edge are pending at any time. Equivalently, after an accepted pulse with delay `d` whose edges no reset cancels, the next rising crossing of `in_clk` comes at least `d + 20 ps` after that pulse's rising crossing, and the next falling crossing at least `d + 20 ps` after its falling crossing. Both intervals are required: a long period alone does not meet the second one when the high time changes from one pulse to the next.
- Relative to each `in_clk` rising crossing, a `load` rising crossing comes at least 1 ps before it or at least 20 ps after it. A load at least 1 ps before a rising crossing, including one less than 20 ps before it, is in effect at that crossing: the pulse that starts there uses the new code and is accepted even if the cell was unloaded before. A load after a rising crossing applies from the next accepted rising crossing. A `load` rising crossing at the same instant as an `in_clk` rising crossing, or less than 1 ps before one, is not a legal stimulus. No code bit crosses `vth` within 20 ps of a `load` rising crossing.
- Every `rst` crossing is at least `max(20 ps, 4*tr)` away from every `in_clk` crossing, every `load` rising crossing, and every scheduled output-edge time, including the times of edges that the reset cancels.

Acceptance uses `epsilon_v = 2 mV` and a timing tolerance `tau_t = 2 ps`. Input crossing times are the `vth` crossings of the observed inputs, located by linear interpolation between saved samples. A loaded code is read from the observed code bits at its `load` crossing. From these, the rules above give the expected output edges `t_e` and the expected level between them.

- Hold: from time 0, or from `t_e + tr + tau_t` after an edge, to `tau_t` before the next edge or to the end of the run, every observed `out_clk` sample is within `epsilon_v` of the expected level.
- Edge: from `t_e - tau_t` to `t_e + tr + tau_t`, `out_clk` stays within `epsilon_v` of the interval from `vss` to `vdd` and does not reverse direction by more than `epsilon_v`. Where the windows of successive edges overlap, which happens only when `tr` is below 4/3 ps, their union is checked as one window. The samples in it must fit the edges taken in order, within `epsilon_v`: each edge moves monotonically from its old level to its new level, starting no earlier than its own `t_e - tau_t` and finishing by its own `t_e + tr + tau_t`. So `out_clk` reverses direction by more than `epsilon_v` only to turn from one edge to the next, and only after the next edge's window has begun.

The observation grid is 2 ps. Final evaluation reruns the public case and adds other inputs and parameter values inside this contract, including conditions that are not in the public case. Every required check must pass. An executed attempt that fails scores 0, and the cause is recorded separately. A missing simulator, or any other execution or infrastructure failure, is not evidence that the model behavior is wrong. If the saved times are too coarse to decide whether a stimulus separation meets its minimum, the case is not graded.

## Deliverable

- Edit `/app/circuit.va` and implement `programmable_delay_cell` on the supplied module and port declarations, including the six parameters.
- Deliver the code loading, pulse, pending-edge, reset, and output behavior in Spec. Any implementation that meets this interface and external behavior is acceptable. A particular state variable, event function, queue, or output operator is not required.
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
