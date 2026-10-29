# Add N/N+1 fractional feedback to a healthy integer loop

Extend the supplied integer PLL so the feedback divider can emit N or N+1 DCO edges per reference interval, and keep the integer behavior when `frac` is 0. The fixed backend is Spectre. The candidate runs as submitted bytes. Task weight is 1.

## Spec

`/app/circuit.va` already contains the complete integer `fractional_pll(ref, rst, n, frac, dco, fb, tune, lock)` source to extend. All ports are electrical nodes referenced to ground. `ref`, `rst`, `n`, `frac`, and `dco` are inputs. `fb`, `tune`, and `lock` are the only candidate outputs. Logic high is 0.9 V. The threshold is 0.45 V.

`healthy_dco(tune, rst, dco)` is instantiated by the fixed bench from `/app/testbench/healthy.va`. Do not modify that file. Its frequency is `20 MHz + sensitivity*tune` plus an environmental frequency disturbance, limited to 20 MHz through 60 MHz. `sensitivity` may vary from 8 MHz/V to 12 MHz/V. The nominal value is 10 MHz/V, which is also the part's default. The fixed DCO adds a frequency offset whose absolute value is at most 2 MHz at 150 µs and removes it at 175 µs. The part's defaults are `frequency_step=0`, `step_start=150 µs`, and `step_end=175 µs`. During the offset the loop must still hold the target frequency ratio. Within 15 µs after the offset is applied, and again within 15 µs after it is removed, the stated frequency, phase, and qualification requirements are met again.

The reference is nominally 10 MHz, so its period is 100 ns. `n` is 3 or 4. `frac` is 0, 0.25, 0.5, or 0.75. A mode change takes effect within 2 ns and clears the division remainder, the partial count, and qualification. While `rst` is high, feedback and qualification are zero. The DCO itself follows the environment reset.

Between adjacent rising `fb` edges there must be exactly N or N+1 rising edges of the actual DCO. When `frac` is 0, only N is allowed. Over each evaluation window, the average interval count may differ from `N+frac` by at most 0.04. A unique accumulator or DSM bit sequence is not required. The real DCO-to-reference frequency-ratio error is at most 0.06. The feedback-to-reference frequency-ratio error is at most 0.015. Each ratio uses the first and last actual edges of the whole observation window.

The fractional path has ordinary phase variation. Phase is measured in cycles of the reference period, not in degrees. Within each evaluation window, take the rising `fb` edges in time order. The first value of `phi` is the signed phase of the first edge relative to its nearest rising reference edge, positive when `fb` follows the reference. Each later edge is measured from its own nearest rising reference edge and then shifted by whole cycles until it differs from the previous value by at most 0.5 cycle. This gives one continuous sequence `phi`. Its sustained mean bias `abs(mean(phi))` is at most 0.2 cycle. This bound takes the mean of the signed sequence first; it is not `mean(abs(phi))`. The peak-to-peak value `max(phi) - min(phi)` of the same sequence is at most 0.35 cycle. Individual edges do not have to coincide. After every mode change or reset, withdraw `lock` within 2 ns. After a mode change, keep `lock` low for the first 1 µs, and regain qualification within 15 µs. While `rst` is high, `fb` and `lock` stay low. That check is the 2 ns effect time plus 200 ps of numerical transition margin. The 15 µs recovery deadline is measured from the actual `n`/`frac` change, from `rst` release, or from a fixed DCO disturbance. It allows 2.2 ns for event response and numerical transition. The checker first checks that `lock` has recovered at the deadline, then checks the original frequency, phase, and 95 percent qualification coverage on the observation window after the deadline. Recovery is not required before the 15 µs deadline. Each mode dwells for 25 µs. The disturbance application and removal each also leave 25 µs for acceptance.

The evaluation windows include the original integer mode, fractional modes, an `n` change, a return to integer, reset recapture, another fractional configuration, and recovery after an in-run DCO frequency disturbance and its removal. `lock` high covers at least 95 percent of a settled window, but the lock bit does not replace the actual frequency and phase criteria. Phase noise, spurs, and a faster lock are not required.

The loop must be tuned from the real feedback error. Do not copy the reference clock onto the feedback output or synthesize the target output clock directly. Reset must clear the control state. Without reset, do not periodically reinitialize in secret. The public bench is `/app/testbench/public-default.scs`. `/app/testbench/acceptance-windows.json` and `/app/testbench/interface.json` are public material. Hidden conditions change only the published ranges above. They do not require a sample-by-sample match to a reference implementation.

Every required acceptance condition must pass. An executed attempt that fails scores 0, and the failure cause is recorded separately. A missing simulator, compile failure, timeout, missing waveform, or other execution or infrastructure failure is not evidence that the submitted model behavior is wrong.

## Deliverable

- Edit `/app/circuit.va`. It is the existing integer PLL, not an empty port shell. You may change the control algorithm, auxiliary modules, and connections inside this file. Keep `fractional_pll` and the port order.
- The candidate outputs are only `tune`, `fb`, and `lock`. `dco` remains an input from `/app/testbench/healthy.va`. The fractional extension must use real DCO edges. Any implementation that meets this interface and external behavior is acceptable. A particular accumulator or event organization is not required.
- Do not edit `/app/testbench/healthy.va`. The submitted model must not copy `ref` to `fb` or generate the target clock without the feedback loop. This restriction applies to the submitted model. You may read the public bench and run the public check.
- `healthy.va` has no transistor device data.

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
