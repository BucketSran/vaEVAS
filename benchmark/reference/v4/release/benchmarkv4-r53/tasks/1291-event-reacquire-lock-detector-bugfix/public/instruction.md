# Event Reacquire Lock Detector Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `event_reacquire_lock_detector.va`:
  - Module `event_reacquire_lock_detector` (entry)
    - position 0: `ref_clk` (input, electrical)
    - position 1: `fb_clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `lock` (output, electrical)
    - position 4: `phase_metric` (output, electrical)
    - position 5: `state_mon` (output, electrical)

## Public Parameter Contract

- `event_reacquire_lock_detector.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `event_reacquire_lock_detector.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `event_reacquire_lock_detector.lock_window` defaults to `180p`; valid range: finite; overrides lock_window.
- `event_reacquire_lock_detector.metric_fullscale` defaults to `600p`; valid range: finite; overrides metric_fullscale.
- `event_reacquire_lock_detector.lock_count` defaults to `3`; valid range: finite; overrides lock_count.
- `event_reacquire_lock_detector.tr` defaults to `60p`; valid range: finite; overrides tr.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RECORD_REFERENCE_CLOCK_RISING_EDGE_TIME`: restore: A rising ref_clk records $abstime. A reset-low rising fb_clk uses the absolute elapsed time since that reference, or metric_fullscale before any reference edge. Required traces: `time`, `fb_clk`, `lock`, `phase_metric`, `ref_clk`, `rst`, `state_mon`.
- `P_REQUIRE_CONSECUTIVE_IN_WINDOW_FEEDBACK_EDGE`: restore: A feedback edge with a recorded reference and phase_error <= lock_window increments the good count capped at lock_count; another feedback edge clears it. lock = vhi exactly when the count reaches lock_count. Required traces: `time`, `fb_clk`, `lock`, `phase_metric`, `ref_clk`, `rst`, `state_mon`.
- `P_CLEAR_LOCK_STATE_AND_PROGRESS_WHEN`: restore: Reset rising or sampled high on a feedback edge clears the good count, lock, phase_metric, and state_mon. Required traces: `time`, `fb_clk`, `lock`, `phase_metric`, `ref_clk`, `rst`, `state_mon`.
- `P_EXPOSE_PHASE_METRIC_AND_STATE_MON`: restore: After each reset-low feedback edge, phase_metric = vhi * clip01(phase_error / metric_fullscale) and state_mon = vhi * clip01(good_count / lock_count). Required traces: `time`, `fb_clk`, `lock`, `phase_metric`, `ref_clk`, `rst`, `state_mon`.
- `P_USE_EVENT_BODY_STATE_UPDATES_PLUS`: restore: Use event-body state updates plus local analog helper functions rather than user task/endtask syntax. Required traces: `time`, `fb_clk`, `lock`, `phase_metric`, `ref_clk`, `rst`, `state_mon`.


The following canonical public behavior is normative for this derived form:

- On each rising `ref_clk` crossing, record `last_ref_time = $abstime`. On each rising `fb_clk` crossing while reset is low, let `phase_error = abs($abstime - last_ref_time)`; before any reference edge, use `metric_fullscale` as the phase error.
- A feedback edge with a recorded reference and `phase_error <= lock_window` increments the consecutive-good count, capped at `lock_count`; any other feedback edge resets the count to zero. Drive `lock = vhi` exactly when the count reaches `lock_count`.
- Clear the consecutive-good count, `lock`, `phase_metric`, and `state_mon` when reset rises or when a feedback edge samples reset high.
- After each reset-low feedback edge, drive `phase_metric = vhi * clip01(phase_error / metric_fullscale)` and `state_mon = vhi * clip01(good_count / lock_count)`, where `clip01` limits its argument to `[0, 1]`.
- Use event-body state updates plus local analog helper functions rather than user task/endtask syntax.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `event_reacquire_lock_detector.va`.
Every supplied `.va` file is editable; do not add or omit files.
