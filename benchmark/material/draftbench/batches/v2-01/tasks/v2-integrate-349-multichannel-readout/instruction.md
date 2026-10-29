# Four-channel sample and sequential readout

Extend the supplied healthy single-channel sample-and-hold into a four-channel capture and sequential readout. The fixed backend is Spectre.

## Spec

Use the module and port order declared in `/app/circuit.va`. The top module is `sample_mux_readout_top`. Its electrical ports, in order, are `ch0`, `ch1`, `ch2`, `ch3`, `clk`, `rst`, `sample`, `read`, `out`, `ch_sel_1`, `ch_sel_0`, and `valid`.

Declare three overrideable real parameters on that top module: `vdd` defaults to 0.9 V, `vth` defaults to 0.45 V, and `tr` defaults to 100 ps. Logic high is `vdd` and logic low is 0. No further numeric interval is declared for these three parameters.

The fixed part is `sample_hold(VDD, VSS, IN, CLK, OUT)` in `/app/testbench/baseline.va`. Its real parameters are `vth` defaulting to 0.45 V and `tedge` defaulting to 100 ps. `OUT` starts at `VSS`. A rising crossing of `vth` by `CLK` relative to `VSS` stores `IN` relative to `VSS`, then `OUT` makes one monotonic transition of duration `tedge`. While the clock is stopped, the held value remains, with no droop. Instantiate that part four times. Tie each `VSS` to 0 and each `VDD` to `vdd`. Reuse those four instances for the sampling duty. Do not copy the part or replace its sampling behavior with another sampler.

Each analog input is stable for at least 1 ns before and after a sampling edge. A sampling-adapter delay of at most 50 ps is allowed. While `rst` is high, sampling is forbidden. The rising edge of `rst`, and any rising edge of `clk` while `rst` is high, clear the read pointer, `out`, both select bits, and `valid`. Those same events clear all four channel frames, including a reset that occurs while the sampling-adapter clock is still high. Clearing finishes within 0.9 ns after the clearing edge crosses `vth`. The fixed hold part has no reset pin. The integration adapter therefore switches all four inputs to 0 during reset and produces one valid sample into the same four parts. After normal mode resumes, those same parts remain in use.

On each rising `clk` edge, a high `sample` captures all four channels at once. A high `read` reads the stored frame in the repeating order 0, 1, 2, 3. `out` holds that frame's selected channel, the select bits identify the channel now on `out`, and `valid` is high. When `sample` and `read` are both high, read the previous frame first and then capture the new frame. When `read` is low, hold `out` and the select bits, drive `valid` low, and do not advance the pointer. `sample` updates only the frame. It must not change the `out` value that is already being held. A later `read` is what presents the new frame.

The fixed part must actually participate. Leaving it in the netlist while driving constants, replaying the test stimulus, or emitting a precomputed answer does not meet the contract. The public check may observe both the pins and the internal hold nodes. Final evaluation checks simultaneous capture, order, pause, refresh, reset, and the original hold behavior from the top-level port waveforms. The voltage tolerance is 3 mV, measured 0.95 ns to 1 ns after the rising `clk` or `rst` edge that causes the event crosses `vth`.

The architecture acceptance version is `sample-hold-causal-v2`. Beyond the healthy-part conditions above, final evaluation may replace the author's `sample_hold` with a same-port diagnostic part. That diagnostic part keeps `OUT` initially 0, a rising threshold `vth` of `CLK` relative to `VSS`, a 100 ps monotonic transition, and hold while the clock is stopped. It changes only the stored value, to 0.75 or 0.6 times `IN` relative to `VSS`. The integration must pass that part's output through unchanged. It must not compensate the diagnostic gain or sample the inputs again to rebuild the frame. The four inputs, simultaneous capture, previous-frame readout, pause, and reset-adapter rules stay the same. A cleared sample of input 0 is still 0 through the diagnostic part. Final evaluation checks each channel's corresponding diagnostic held value from the top-level ports, still within 3 mV. This rule checks that the part actually participates. It is not a source-similarity or instance-count score.

The public representative bench is `/app/testbench/public-default.scs`, together with `/app/testbench/cases.json`. Final evaluation may change stimuli inside this contract. It does not add a new sampling rule. Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va`. The starter declares `sample_mux_readout_top` and its port order. Implement the parameters and the integration behavior there.
- Additional adapter, control, and connection modules may be added inside `/app/circuit.va`. The number of modules is not fixed. No other file is collected. Any organization that keeps the declared interface, instantiates the fixed `sample_hold` four times, and meets the external behavior is acceptable. A particular internal state variable or event operator is not required.
- `/app/testbench/baseline.va` is a fixed development part. Do not edit it. The submitted model must call that part for sampling and must not replace the call with constants, the test stimulus, or a precomputed frame. This restriction applies to the submitted model. You may still read the public bench and run the public check.
- The causal diagnostic substitution is an evaluation of the same pins. Do not add a second sampler to defeat it.

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
