# Response-driven comparator offset search

Build a Verilog-A search instrument for a fixed, read-only comparator. The fixed backend is Spectre. Candidate source runs as submitted bytes, and the syntax is that backend's Verilog-A. A correct report of a DUT that misses its own performance limit still passes. The instrument is what is scored.

## Spec

Use the module and port order in `/app/circuit.va`. The module is `offset_search(dcmpp, ready, vinp, vinn, request, offset_est, valid, status)`. `dcmpp` and `ready` are read-only observation inputs. Do not drive them. `vinp`, `vinn`, `request`, `offset_est`, `valid`, and `status` are outputs.

Declare these parameters and defaults: real `step_initial=0.064` V, integer `iterations=7`, real `gap=1 ns`, real `timeout=10 ns`, and real `tr=20 ps`. The search step, iteration count, gap, and timeout stay at these defaults. No further numeric interval is declared for them.

The estimate starts at 0. The differential input equals the estimate and is symmetric about 0.5 V. At 1 ns, raise the first `request` pulse. After the comparator receives `request`, it returns a `dcmpp` decision and a rising `ready`. Update the estimate only on a rising `ready`: if `dcmpp` is above 0.5 V, subtract the current step; otherwise add the step. The step then halves. Do this seven times. After a response, drop `request` immediately and issue the next `request` after `gap`. After the last response, set `valid=1` and `status=1`, stop stimulating, and hold the result. If any `request` still has no `ready` after `timeout`, set `status=2` and `valid=0`, stop, and hold the unfinished estimate. `status=0` means the search is still running.

The decision threshold and logic high are 0.5 V and 1 V. The timing allowance is 80 ps and the voltage tolerance is 1.5 mV. Do not advance from a fixed expected-response table. The search range is ±0.127 V. A DUT outside that range is a publicly uncovered condition.

The first rising `request` crossing of 0.5 V must lie within 80 ps of 1.01 ns, where an edge that starts at 1 ns with the default 20 ps transition crosses. A response is the first rising `ready` crossing of 0.5 V after a rising `request` crossing and before the next one. Each later rising `request` crossing must lie within 80 ps of the preceding response plus `gap`. The timeout is counted from the rising `request` crossing. All six outputs, including `request`, `vinp`, and `vinn`, are scored as reports. The timing allowance also applies around these events: every rising `request` crossing, every response, and every timeout instant. These events, together with the start and the end of the transient, divide the run into intervals. An interval no longer than 160 ps is not scored. In every longer interval, each output is scored at every saved point more than 80 ps from both ends of the interval, and at the midpoint of the interval, where its value is interpolated linearly between saved points.

The read-only DUT is `response_comparator` in `/app/testbench/dut/comparator.va`. Its declared defaults are real `offset=0.023`, `td=200 ps`, `tr=20 ps`, and integer `drop_after=99`. Public DUT conditions use an offset from -0.06 V to 0.06 V, a response delay from 150 ps to 700 ps, and a `ready` pulse width of 400 ps. The DUT may stop responding after any completed response. In every case, public and final, no interval is exactly 160 ps long. Those DUT settings and any expected-response table must not replace a real `ready`.

Public cases are in `/app/testbench/cases.json`. Final evaluation, after submission, uses different parameters, events, and fault instances inside this contract. Its bench is not a solving aid. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va` and implement `offset_search` on the declared ports. Declare the parameters above.
- Deliver the search stimulus and the report. Any implementation that meets this interface and external behavior is acceptable. A particular internal state variable or event organization is not required.
- Do not drive `dcmpp` or `ready`, and do not edit `/app/testbench/dut/comparator.va`. The submitted model must not step from a stored expected-response table. This restriction applies to the submitted model. You may read the public DUT and run the public check.
- Reporting the measured result, including `status=2` when the DUT stops responding, is the task. The DUT's own offset error is not an instrument failure.

Run `python3 /app/testbench/check.py --output /app/output/public-check`. The [public testbench guide](/app/testbench/README.md) documents the Spectre dependency, case selection, timeouts, output layout, and diagnostic exit codes. Public feedback is not the final task score.

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
