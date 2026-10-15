# Form-Specific Workflows

## DUT Authoring

1. Match the required file, module, ports, parameters, and supply/threshold conventions.
2. Run the fixed visible deck before broad refactoring.
3. Diagnose in this order: include/module binding, declarations, initialization, event detection, state update, output contribution, waveform behavior.
4. At each relevant event, compare the trace just before and just after the event against an explicit instruction invariant.
5. After the final edit, rerun the fixed deck and audit boundary cases that the public trace may not cover.

## Bug Fixing

1. Copy or preserve the supplied buggy bundle in the submission as required by the runtime.
2. Reproduce the public failure before editing; record the earliest failing layer and evidence.
3. Trace the failure backward to the smallest responsible statement or state transition.
4. Preserve module interface, filenames, unrelated behavior, and public support bindings.
5. Apply one causal repair. Avoid opportunistic rewrites that make attribution impossible.
6. Rerun the original failing deck, then recheck initialization and adjacent event/timing cases.

## Testbench Authoring

1. Inspect the supplied DUT interface and the candidate include/binding rule.
2. Make the testbench self-contained within the declared public fixture root.
3. Exercise the `reference` case first to establish that sources, bindings, transient setup, saves, and measurements execute.
4. Run all five public mutation fixtures. Compare what the testbench observes, not the mutation names themselves.
5. Ensure required nodes are saved and observations occur after meaningful settling/event windows.
6. Keep pass/fail logic, if authored, derived from public task requirements rather than hidden assumptions.

For every form, separate three statements in the final assessment:

- what the public command executed;
- what explicit public invariant was observed;
- what remains unknown until private Spectre scoring.
