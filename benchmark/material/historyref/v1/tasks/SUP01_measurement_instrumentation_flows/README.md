# CT07 Measurement Instrumentation Flows

SUP01 covers voltage-domain behavioral measurement helpers and measurement
flows. The category is intentionally not a catch-all for arbitrary testbenches:
each retained entry must expose a measurable waveform or file-backed metric
that can be checked by EVAS and Spectre on the same public observables.

| ID | Entry | Level | Circuit role | Why kept | Primary behavior checks |
| --- | --- | --- | --- | --- | --- |
| CT07-01 | `vbr1_l1_crossing_metric_writer` | L1 | Crossing detector that writes the measured crossing time to a metric file. | Exercises event-triggered measurement plus simulator side-output handling. | `first_crossing_time_reported`, `metric_file_matches_waveform_crossing` |
| CT07-02 | `vbr1_l1_edge_interval_timer` | L1 | Measures the interval between two public crossing events and reports it as an output voltage. | Covers event-to-metric timing instrumentation without adding a larger system loop. | `cross_interval_163p333` |
| CT07-03 | `vbr1_l1_gain_estimator` | L1 | Timer-sampled measurement helper that estimates differential gain from input/output spans and reports `gain_out` plus `valid`. | Covers reusable waveform-to-metric instrumentation without duplicating the L2 gain-extraction signal path. | `valid_asserts_after_observation_window`, `waveform_gain_is_about_six`, `gain_out_matches_waveform_derived_gain` |
| CT07-04 | `vbr1_l1_peak_detector` | L1 | Tracks running extrema of a transient waveform. | Covers stateful measurement of dynamic signal range. | `running_peak_tracks_input_extrema` |
| CT07-05 | `vbr1_l1_settling_time_detector` | L1 | Detects whether a transient response settles inside a public tolerance window. | Covers measurement of time-domain convergence against a tolerance band. | `settling_window_metric` |
| CT07-06 | `vbr1_l2_gain_extraction_convergence_measurement_flow` | L2 | Source, deterministic dither, fixed-gain amplifier, and gain extraction measurement flow. | Kept as a composed source, deterministic dither, fixed-gain amplifier, and waveform-derived gain measurement flow. | `gain_amplification_present`, `differential_gain_above_threshold` |
| CT07-07 | `vbr1_l2_measurement_flow` | L2 | Edge-counting measurement flow that normalizes a final metric and writes `candidate.out`. | Covers a complete metric path: events, final-step normalization, and file-backed result. | `ref_edges_counted_on_expected_grid`, `metric_out_normalizes_final_edge_count`, `final_step_writes_candidate_metric_file` |

Audit rule: SUP01 entries should remain measurement-centric. If a future entry
is only a generic harness with no measured metric, it belongs outside the strong
benchmark claims.
