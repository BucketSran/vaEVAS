# Quadrature LO generator from a divided clock

Build a divide-by-four quadrature LO generator that steps through a fixed four-state sequence on qualified clock edges and asserts a qualification flag after two full traversals.

## Spec

Use the starter declaration of `quadrature_lo_generator_divided_clock`. Every top-level port is electrical. The positional order is `clk_in`, `rst`, `enable`, `lo_i`, `lo_q`, `div_metric`, `quad_ok`. The top module must expose exactly this port order. Optional implementation-local helper modules are allowed, but the public contract requires no helper module.

`clk_in`, `rst`, and `enable` are inputs. The model drives `lo_i`, `lo_q`, `div_metric`, and `quad_ok`.

Declare these overrideable parameters on the top module and pass compatible values to any helper module that needs them.

- `vdd` = 0.9 V. Logic-high output level.
- `vss` = 0.0 V. Logic-low output level.
- `vth` = 0.45 V. Threshold for `clk_in`, `rst`, and `enable`.
- `tr` = 200 ps. Output transition smoothing time. The qualification output also uses it.

All outputs start at `vss`. On reset or while disabled, clear `lo_i`, `lo_q`, `div_metric`, and `quad_ok`. Every reset or disable clears the phase asynchronously. Releasing the controls does not advance the sequence; the first new qualified clock edge outputs `10`.

A qualified rising edge is a rising `clk_in` edge while `rst` is low and `enable` is high. On successive qualified edges, generate the repeating state sequence `(lo_i, lo_q) = 10, 11, 01, 00`. Each state lasts one input clock period, so both outputs divide the input clock by four, have the same divided frequency, and `lo_q` trails `lo_i` by one quarter of the divided-clock period. `div_metric` exposes the state index `k` of the currently driven pair as `vss + (vdd - vss) * k / 3`, where the sequence above uses `k = 0..3`.

After a reset or a re-enable, counting restarts from the first qualified edge. `quad_ok` stays at `vss` on the first through seventh qualified edges and updates to `vdd` on the eighth, when the second traversal of `10, 11, 01, 00` enters `00`. It does not wait for a ninth edge back at `10`. `quad_ok` stays asserted until reset or disable.

Initial levels and edges are unambiguous. `clk_in`, `rst`, and `enable` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. Independent control edges are at least `2*tr` apart. Supplies stay fixed. The control threshold is `vth`. Simultaneous events that this contract does not define are not scored.

Voltage error is at most 2 mV. Each output reaches its new value within `tr` after the event that changes it. Every saved point is scored, for all four outputs, except points less than `1.15*tr` after t = 0 or after an event that changes an output target: a qualified rising `clk_in` edge, or a clear by a rising `rst` or a falling `enable`. A scored waveform uses a time step no coarser than one quarter of the shortest output transition. Final evaluation may change inputs and parameters inside this contract.

An executed attempt that fails a required check scores 0. The failure cause is recorded separately. A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong. Acceptance uses the fixed Spectre backend.

## Deliverable

- Edit `/app/circuit.va` and implement `quadrature_lo_generator_divided_clock` on the module and positional ports in the starter. Any helper module goes in the same file.
- Any Verilog-A implementation is acceptable when it meets that interface and the external behavior in Spec. The state sequence and the qualification count define the observable outputs. They do not require a particular state name or event operator.
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
