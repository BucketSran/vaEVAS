# vaBench 300 Benchmark Overview

Date: 2026-06-23

This is the single navigation surface for the benchmark. The primary management manifest is the vaBench 300 manifest; release-v1 rows are composition/provenance, not a separate benchmark denominator.

## Headline Counts

| Question | Answer | Evidence |
| --- | ---: | --- |
| vaBench management rows | 300 | `benchmark-vabench-release-v1/vabench-300-expansion/VABENCH_300_MANIFEST.json` |
| paper-score-ready rows | 300 | `benchmark-vabench-release-v1/vabench-300-expansion/VABENCH_300_MANIFEST.json` |
| pending certification rows | 0 | `benchmark-vabench-release-v1/vabench-300-expansion/VABENCH_300_MANIFEST.json` |
| score-counted rows | 265 | `benchmark-vabench-release-v1/vabench-300-expansion/VABENCH_300_MANIFEST.json` |
| inherited v1 rows + fresh-certified v1.1 rows | 271 + 29 | `benchmark-vabench-release-v1/vabench-300-expansion/VABENCH_300_MANIFEST.json` |
| partial-pass negative candidates | 1500 | `benchmark-vabench-release-v1/vabench-300-expansion/VABENCH_300_MANIFEST.json` |
| current Spectre reference dual PASS | 300 / 300 | `results/vabench-300-dual-reference-rust-checker29-full-20260622/summary.json` |
| current Spectre reference no-checker rows | 0 | `results/vabench-300-dual-reference-rust-checker29-full-20260622/summary.json` |
| EVAS PASS / Spectre FAIL mismatches | 0 | `benchmark-vabench-release-v1/reports/dual_certification.json` plus current full-300 summaries |

## Backend Coverage

Four-backend certification status: `pass`. Full-300 runs completed for 4 / 4 backend rows; currently claimable full-300 behavior certification exists for 4 / 4.

| Backend | Full-300 Status | Rows | Evidence | Notes |
| --- | --- | ---: | --- | --- |
| Spectre reference + EVAS Rust dual | `pass` | 300 / 300 | `results/vabench-300-dual-reference-rust-checker29-full-20260622/summary.json` | dual PASS 300/300; Spectre ok 300/300; 0 rows lack behavior checkers. |
| Spectre AX + EVAS Rust dual | `pass` | 300 / 300 | `results/vabench-300-dual-ax-rust-checker29-full-20260622/summary.json` | dual PASS 300/300; Spectre ok 300/300; 0 rows lack behavior checkers. |
| EVAS Rust only | `pass` | 300 / 300 | `results/vabench-300-evas-rust-full-checker29-metaraw-20260622/summary.json` | compile/sim PASS 300/300; behavior checker PASS 300/300; missing/nonpass 0/300. |
| EVAS Python only | `pass` | 300 / 300 | `results/vabench-300-evas-python-full-checker29-metaraw-20260622/summary.json` | compile/sim PASS 300/300; behavior checker PASS 300/300; missing/nonpass 0/300. |

## Equivalence Contract

- Bit-exact equality claim: `not_asserted`.
- Acceptance basis: behavior/spec pass plus EVAS/Spectre waveform or task-metric parity.
- Waveform small-absolute gate: `max_rmse_v<=0.05 and max_abs_v<=0.30`.
- Waveform relative-RMS gate: `row_mean_relative_rms_error<=0.10 and worst_signal_relative_rms_error<=0.22; or row_mean_relative_rms_error<=0.08 and worst_signal_relative_rms_error<=0.25`.
- Edge-window policy: core_v2 rows may exclude a bounded edge/discontinuity window only when local to signal activity, at most 8% of the common sample grid, and stable-region error remains small; raw metrics remain reported.
- Gain metric gate: `evas_gain>4 and spectre_gain>4 and relative_gain_delta<=0.25`.
- PLL task-aware rows: PLL rows use task-level lock/frequency/control metrics; status=passed is the certification gate for those special rows.

## Observed Parity Metrics

| Metric | Value |
| --- | ---: |
| certified/pass rows | 300 / 300 |
| detailed waveform-metric rows | 292 |
| gain-metric forms | 4 |
| PLL task-aware forms | 4 |
| max row mean relative RMS error | 0.0172 |
| max worst-signal relative RMS error | 0.148 |
| max RMSE voltage | 0.141 V |
| max absolute voltage error | 1 V |
| max digital mismatch ratio | 0.02 |
| max relative gain delta | 0.0208 |

## Management Surface

Use 300 as the asset-management and certified-task row count. The paper-facing score-ready surface is now 300 rows; 29 fresh-certified v1.1 rows are admitted through the score-denominator audit. Staging bundle counts are execution inputs, not benchmark size.

| Count | Value | Meaning |
| --- | ---: | --- |
| management rows | 300 | asset-management and simulator-certified surface |
| paper-score-ready rows | 300 | rows admitted to the current paper-facing score surface |
| fresh-certified score-admitted v1.1 rows | 29 | admitted by v1.1 score admission audit |
| task-specific v1.1 EVAS gold pass | 29 | local EVAS full-checker evidence |
| task-specific v1.1 fresh Spectre pass | 29 | fresh Spectre + EVAS dual rerun evidence |
| task-specific v1.1 negative full-checker fail | 145 | local negative quality evidence for v1.1 rows |
| score-counted rows | 265 | current counted score surface |
| negative candidates | 1500 | static-shape audited partial-pass candidates |
| runnable staging bundles | 0 | execution inputs only; not a benchmark count |

Promotion note: This is the primary vaBench 300 management surface: 271 inherited certified v1 rows plus 29 task-specific v1.1 rows with fresh EVAS/Spectre PASS evidence. After score-denominator admission, all 300 rows are simulator-certified assets and 265 core rows are counted in the paper-facing model-evaluation denominator after support-suite exclusions.

## Category Overview

| Category | Entries | Forms | Core | Support | L1 | L2 | Scored Entries | Certified Entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseband Signal Conditioning | 8 | 30 | 8 | 0 | 7 | 1 | 8 | 8 |
| Bias Reference and Power Management | 9 | 32 | 9 | 0 | 6 | 3 | 9 | 9 |
| Calibration, DEM, and Control | 7 | 26 | 7 | 0 | 6 | 1 | 7 | 7 |
| Comparator and Decision Circuits | 9 | 34 | 9 | 0 | 7 | 2 | 9 | 9 |
| Data Converter Models | 15 | 52 | 15 | 0 | 10 | 5 | 15 | 15 |
| Measurement Instrumentation Flows | 7 | 17 | 0 | 7 | 5 | 2 | 0 | 7 |
| PLL Clock and Timing Systems | 11 | 41 | 11 | 0 | 8 | 3 | 11 | 11 |
| RF and AFE Behavioral Macromodels | 8 | 28 | 8 | 0 | 5 | 3 | 8 | 8 |
| Sampling and Analog Memory | 6 | 22 | 6 | 0 | 5 | 1 | 6 | 6 |
| Stimulus and Source Generators | 6 | 18 | 0 | 6 | 5 | 1 | 0 | 6 |

## Complete Entry List

| Entry | Level | Track | Difficulty | Category | Base function | Forms | Score | EVAS/Spectre | Parity summary |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `vbr11_l1_bootstrapped_sample_switch` | L1 | core | D2 | Sampling and Analog Memory | Bootstrapped sample switch abstraction | 4 | counted | pass/pass | wave 4/4, mean<=2.996e-05, worst<=1.396e-04, abs<=5.914e-04V |
| `vbr11_l1_sigma_delta_modulator_loop` | L1 | core | D3 | Data Converter Models | First-order sigma-delta modulator loop | 4 | counted | pass/pass | wave 4/4, mean<=3.722e-05, worst<=1.713e-04, abs<=7.685e-04V |
| `vbr11_l2_bandgap_startup_trim_flow` | L2 | core | D3 | Bias Reference and Power Management | Bandgap startup and trim convergence flow | 4 | counted | pass/pass | wave 4/4, mean<=5.777e-06, worst<=1.961e-05, abs<=5.310e-05V |
| `vbr11_l2_fractional_n_pll_divider_flow` | L2 | core | D3 | PLL Clock and Timing Systems | Fractional-N divider and accumulator flow | 4 | counted | pass/pass | wave 4/4, mean<=1.872e-05, worst<=5.044e-05, abs<=2.461e-04V |
| `vbr11_l2_metastability_window_comparator_flow` | L2 | core | D3 | Comparator and Decision Circuits | Comparator metastability window model | 4 | counted | pass/pass | wave 4/4, mean<=1.777e-05, worst<=5.642e-05, abs<=2.308e-04V |
| `vbr11_l2_quadrature_iq_imbalance_corrector` | L2 | core | D3 | RF and AFE Behavioral Macromodels | Quadrature gain/phase imbalance corrector | 4 | counted | pass/pass | wave 4/4, mean<=4.856e-05, worst<=2.280e-04, abs<=9.852e-04V |
| `vbr11_l2_time_interleaved_adc_mismatch_flow` | L2 | core | D3 | Data Converter Models | Time-interleaved ADC mismatch observation flow | 4 | counted | pass/pass | wave 4/4, mean<=8.082e-05, worst<=3.455e-04, abs<=0.00176V |
| `vbr1_l1_acquisition_limited_sample_and_hold` | L1 | core | D2 | Sampling and Analog Memory | Acquisition-limited sample-and-hold | 4 | counted | pass/pass | wave 4/4, mean<=5.287e-08, worst<=2.548e-07, abs<=3.226e-06V |
| `vbr1_l1_aperture_delay_track_and_hold` | L1 | core | D2 | Sampling and Analog Memory | Aperture-delay track-and-hold | 4 | counted | pass/pass | wave 4/4, mean<=1.869e-06, worst<=3.706e-06, abs<=8.871e-05V |
| `vbr1_l1_bandgap_reference_macro_model` | L1 | core | D2 | Bias Reference and Power Management | Bandgap reference macro model | 4 | counted | pass/pass | wave 4/4, mean<=2.306e-06, worst<=5.933e-06, abs<=1.125e-04V |
| `vbr1_l1_bang_bang_phase_detector` | L1 | core | D2 | PLL Clock and Timing Systems | Bang-bang phase detector | 4 | counted | pass/pass | wave 4/4, mean<=5.000e-04, worst<=0.0025, abs<=1V |
| `vbr1_l1_bias_voltage_generator_with_enable_trim` | L1 | core | D1 | Bias Reference and Power Management | Bias voltage generator with enable/trim | 4 | counted | pass/pass | wave 4/4, mean<=1.149e-06, worst<=5.743e-06, abs<=8.784e-05V |
| `vbr1_l1_binary_weighted_voltage_dac` | L1 | core | D1 | Data Converter Models | Simple 4-bit binary-coded DAC | 4 | counted | pass/pass | wave 4/4, mean<=0.001, worst<=0.00502, abs<=0.0267V |
| `vbr1_l1_burst_clock_source` | L1 | support | D2 | Stimulus and Source Generators | Burst clock source | 3 | not counted | pass/pass | wave 3/3, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_calibration_deadband_controller` | L1 | core | D2 | Calibration, DEM, and Control | Calibration deadband controller | 4 | counted | pass/pass | wave 4/4, mean<=7.596e-06, worst<=3.796e-05, abs<=3.357e-04V |
| `vbr1_l1_capacitive_weighted_sar_feedback_dac` | L1 | core | D2 | Data Converter Models | Capacitive/weighted SAR feedback DAC | 4 | counted | pass/pass | wave 4/4, mean<=1.773e-06, worst<=4.433e-06, abs<=3.747e-05V |
| `vbr1_l1_charge_pump_abstraction` | L1 | core | D2 | PLL Clock and Timing Systems | Voltage-domain charge-pump control abstraction | 4 | counted | pass/pass | wave 4/4, mean<=1.160e-06, worst<=4.419e-06, abs<=3.750e-05V |
| `vbr1_l1_clock_divider` | L1 | core | D2 | PLL Clock and Timing Systems | Clock divider | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_clocked_adc_quantizer` | L1 | core | D2 | Data Converter Models | Clocked ADC quantizer | 4 | counted | pass/pass | wave 4/4, mean<=1.598e-09, worst<=7.989e-09, abs<=4.999e-08V |
| `vbr1_l1_clocked_sample_and_hold` | L1 | core | D2 | Sampling and Analog Memory | Clocked sample-and-hold | 4 | counted | pass/pass | wave 4/4, mean<=5.424e-07, worst<=1.619e-06, abs<=4.046e-05V |
| `vbr1_l1_crossing_metric_writer` | L1 | support | D2 | Measurement Instrumentation Flows | Crossing metric writer | 3 | not counted | pass/pass | wave 3/3, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_dac_mismatch_unit_weighting_model` | L1 | core | D2 | Data Converter Models | DAC mismatch/unit-weighting model | 4 | counted | pass/pass | wave 4/4, mean<=0.00167, worst<=0.00834, abs<=0.176V |
| `vbr1_l1_debounce_latch` | L1 | core | D2 | Comparator and Decision Circuits | Comparator debounce latch | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_digital_phase_accumulator_with_modulo_wrap` | L1 | core | D2 | PLL Clock and Timing Systems | Digital phase accumulator with modulo wrap | 4 | counted | pass/pass | wave 4/4, mean<=1.242e-15, worst<=2.484e-15, abs<=2.975e-14V |
| `vbr1_l1_dither_or_noise_like_deterministic_source` | L1 | support | D2 | Stimulus and Source Generators | Dither or noise-like deterministic source | 3 | not counted | pass/pass | wave 3/3, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_dwa_dem_encoder` | L1 | core | D2 | Calibration, DEM, and Control | DWA/DEM encoder | 4 | counted | pass/pass | wave 4/4, mean<=1.748e-06, worst<=6.642e-05, abs<=6.601e-04V |
| `vbr1_l1_edge_interval_timer` | L1 | support | D2 | Measurement Instrumentation Flows | Edge interval timer | 2 | not counted | pass/pass | wave 2/2, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_element_shuffler` | L1 | core | D2 | Calibration, DEM, and Control | Element shuffler | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_first_order_lowpass` | L1 | core | D1 | Baseband Signal Conditioning | First-order lowpass | 4 | counted | pass/pass | wave 4/4, mean<=1.597e-08, worst<=3.194e-08, abs<=4.994e-08V |
| `vbr1_l1_gain_estimator` | L1 | support | D2 | Measurement Instrumentation Flows | Gain estimator | 2 | not counted | pass/pass | gain delta<=2.000e-07 |
| `vbr1_l1_gain_trim_controller` | L1 | core | D2 | Calibration, DEM, and Control | Gain trim controller | 4 | counted | pass/pass | wave 4/4, mean<=1.842e-07, worst<=9.209e-07, abs<=5.040e-06V |
| `vbr1_l1_higher_order_filter` | L1 | core | D2 | Baseband Signal Conditioning | Higher-order filter | 4 | counted | pass/pass | wave 4/4, mean<=3.151e-06, worst<=1.034e-05, abs<=8.511e-05V |
| `vbr1_l1_hysteresis_comparator` | L1 | core | D2 | Comparator and Decision Circuits | Hysteresis comparator | 4 | counted | pass/pass | wave 4/4, mean<=4.167e-04, worst<=8.333e-04, abs<=1V |
| `vbr1_l1_ldo_regulator_macro_model` | L1 | core | D2 | Bias Reference and Power Management | LDO regulator macro model | 4 | counted | pass/pass | wave 4/4, mean<=6.567e-16, worst<=3.283e-15, abs<=5.301e-14V |
| `vbr1_l1_lfsr_prbs_generator` | L1 | support | D2 | Stimulus and Source Generators | PRBS stimulus/dither generator | 4 | not counted | pass/pass | wave 4/4, mean<=1.555e-04, worst<=4.664e-04, abs<=0.00714V |
| `vbr1_l1_limiting_amplifier_frontend` | L1 | core | D1 | RF and AFE Behavioral Macromodels | Limiting amplifier front-end | 4 | counted | pass/pass | wave 4/4, mean<=1.385e-06, worst<=6.924e-06, abs<=9.363e-05V |
| `vbr1_l1_lna_gain_compression_macro` | L1 | core | D2 | RF and AFE Behavioral Macromodels | LNA gain/compression macro | 4 | counted | pass/pass | wave 4/4, mean<=1.386e-06, worst<=6.929e-06, abs<=9.378e-05V |
| `vbr1_l1_lock_detector` | L1 | core | D2 | PLL Clock and Timing Systems | Lock detector | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_log_rssi_power_detector` | L1 | core | D3 | RF and AFE Behavioral Macromodels | Log/RSSI power detector | 4 | counted | pass/pass | wave 4/4, mean<=1.524e-06, worst<=4.802e-06, abs<=5.250e-05V |
| `vbr1_l1_loop_filter_abstraction` | L1 | core | D2 | PLL Clock and Timing Systems | Sampled loop-filter abstraction | 4 | counted | pass/pass | wave 4/4, mean<=8.683e-06, worst<=4.339e-05, abs<=4.335e-04V |
| `vbr1_l1_offset_comparator` | L1 | core | D1 | Comparator and Decision Circuits | Offset comparator | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_pa_compression_macro` | L1 | core | D3 | RF and AFE Behavioral Macromodels | PA compression macro | 4 | counted | pass/pass | wave 4/4, mean<=1.396e-06, worst<=6.978e-06, abs<=1.028e-04V |
| `vbr1_l1_peak_detector` | L1 | support | D2 | Measurement Instrumentation Flows | Peak detector | 4 | not counted | pass/pass | wave 4/4, mean<=0.0132, worst<=0.0396, abs<=0.549V |
| `vbr1_l1_pfd_up_dn_logic` | L1 | core | D2 | PLL Clock and Timing Systems | PFD UP/DN logic | 4 | counted | pass/pass | wave 4/4, mean<=1.779e-09, worst<=5.467e-09, abs<=4.569e-08V |
| `vbr1_l1_pipeline_adc_stage` | L1 | core | D3 | Data Converter Models | Pipeline ADC MDAC stage | 4 | counted | pass/pass | wave 4/4, mean<=8.324e-07, worst<=4.995e-06, abs<=2.249e-05V |
| `vbr1_l1_power_on_reset_detector` | L1 | core | D2 | Bias Reference and Power Management | Power-on-reset detector | 4 | counted | pass/pass | wave 4/4, mean<=1.437e-06, worst<=7.183e-06, abs<=1.125e-04V |
| `vbr1_l1_precision_rectifier_envelope_detector` | L1 | core | D2 | Baseband Signal Conditioning | Precision rectifier/envelope detector | 4 | counted | pass/pass | wave 4/4, mean<=0.00388, worst<=0.0125, abs<=1V |
| `vbr1_l1_programmable_gain_amplifier` | L1 | core | D2 | Baseband Signal Conditioning | Programmable gain amplifier | 4 | counted | pass/pass | wave 4/4, mean<=0.00746, worst<=0.0248, abs<=1V |
| `vbr1_l1_propagation_delay_comparator` | L1 | core | D2 | Comparator and Decision Circuits | Propagation-delay comparator | 4 | counted | pass/pass | wave 4/4, mean<=1.611e-05, worst<=9.468e-05, abs<=0.104V |
| `vbr1_l1_ptat_ctat_reference_generator` | L1 | core | D2 | Bias Reference and Power Management | PTAT/CTAT reference generator | 4 | counted | pass/pass | wave 4/4, mean<=2.047e-06, worst<=6.970e-06, abs<=7.354e-05V |
| `vbr1_l1_ramp_or_step_source` | L1 | support | D2 | Stimulus and Source Generators | Periodic phase-ramp guard source | 3 | not counted | pass/pass | wave 3/3, mean<=0.0147, worst<=0.0158, abs<=1V |
| `vbr1_l1_resettable_integrator` | L1 | core | D2 | Baseband Signal Conditioning | Resettable integrator | 4 | counted | pass/pass | wave 4/4, mean<=0.0172, worst<=0.0515, abs<=0.388V |
| `vbr1_l1_rf_mixer_downconverter_macro` | L1 | core | D2 | RF and AFE Behavioral Macromodels | RF mixer/downconverter macro | 4 | counted | pass/pass | wave 4/4, mean<=0.0097, worst<=0.0485, abs<=0.164V |
| `vbr1_l1_sample_and_hold_with_droop_leakage` | L1 | core | D2 | Sampling and Analog Memory | Sample-and-hold with droop/leakage | 4 | counted | pass/pass | wave 4/4, mean<=0.00178, worst<=0.0071, abs<=0.085V |
| `vbr1_l1_sar_logic` | L1 | core | D2 | Data Converter Models | SAR logic | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_segmented_dac` | L1 | core | D2 | Data Converter Models | Segmented DAC | 4 | counted | pass/pass | wave 4/4, mean<=0.00217, worst<=0.013, abs<=0.141V |
| `vbr1_l1_settling_time_detector` | L1 | support | D2 | Measurement Instrumentation Flows | Settling response measurement helper | 2 | not counted | pass/pass | wave 2/2, mean<=1.109e-08, worst<=3.326e-08, abs<=4.996e-08V |
| `vbr1_l1_sine_periodic_voltage_source` | L1 | support | D1 | Stimulus and Source Generators | Sine/periodic voltage source | 3 | not counted | pass/pass | wave 3/3, mean<=2.575e-04, worst<=2.575e-04, abs<=2.022e-04V |
| `vbr1_l1_slew_rate_limiter` | L1 | core | D2 | Baseband Signal Conditioning | Slew-rate limiter | 4 | counted | pass/pass | wave 4/4, mean<=0.00489, worst<=0.00979, abs<=0.015V |
| `vbr1_l1_soft_hysteretic_limiter` | L1 | core | D2 | Baseband Signal Conditioning | Soft/hysteretic limiter | 4 | counted | pass/pass | wave 4/4, mean<=1.128e-05, worst<=3.625e-05, abs<=2.825e-04V |
| `vbr1_l1_strongarm_style_latch_comparator` | L1 | core | D2 | Comparator and Decision Circuits | StrongARM-style latch comparator | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_successive_approximation_calibration_search_fsm` | L1 | core | D2 | Calibration, DEM, and Control | Successive-approximation calibration/search FSM | 4 | counted | pass/pass | wave 4/4, mean<=1.750e-04, worst<=8.333e-04, abs<=1V |
| `vbr1_l1_thermometer_code_decoder` | L1 | core | D1 | Data Converter Models | Thermometer-code decoder | 4 | counted | pass/pass | wave 4/4, mean<=4.762e-04, worst<=0.00167, abs<=1V |
| `vbr1_l1_threshold_comparator` | L1 | core | D1 | Comparator and Decision Circuits | Threshold comparator | 4 | counted | pass/pass | wave 4/4, mean<=0, worst<=0, abs<=0V |
| `vbr1_l1_trim_calibration_controller` | L1 | core | D2 | Calibration, DEM, and Control | Trim-voltage generator | 4 | counted | pass/pass | wave 4/4, mean<=8.065e-07, worst<=3.226e-06, abs<=6.000e-06V |
| `vbr1_l1_unit_element_thermometer_dac` | L1 | core | D1 | Data Converter Models | Unit-element thermometer DAC | 4 | counted | pass/pass | wave 4/4, mean<=6.050e-04, worst<=0.00968, abs<=0.156V |
| `vbr1_l1_uvlo_brownout_detector` | L1 | core | D1 | Bias Reference and Power Management | UVLO/brownout detector | 4 | counted | pass/pass | wave 4/4, mean<=3.416e-16, worst<=1.708e-15, abs<=7.105e-15V |
| `vbr1_l1_vco_phase_integrator` | L1 | core | D2 | PLL Clock and Timing Systems | VCO phase integrator | 4 | counted | pass/pass | wave 4/4, mean<=2.275e-10, worst<=6.824e-10, abs<=2.345e-08V |
| `vbr1_l1_window_comparator_detector` | L1 | core | D2 | Comparator and Decision Circuits | Window comparator/detector | 4 | counted | pass/pass | wave 4/4, mean<=4.167e-04, worst<=8.333e-04, abs<=1V |
| `vbr1_l2_adpll_lock_ratio_hop_timer_flow` | L2 | core | D3 | PLL Clock and Timing Systems | ADPLL lock/ratio-hop/timer flow | 2 | counted | pass/pass | task metrics 2 forms |
| `vbr1_l2_agc_receiver_leveling_loop` | L2 | core | D3 | RF and AFE Behavioral Macromodels | AGC receiver leveling loop | 2 | counted | pass/pass | wave 2/2, mean<=1.743e-06, worst<=5.529e-06, abs<=1.065e-04V |
| `vbr1_l2_amplifier_filter_chain` | L2 | core | D3 | Baseband Signal Conditioning | Amplifier/filter chain | 2 | counted | pass/pass | wave 2/2, mean<=7.331e-06, worst<=2.111e-05, abs<=2.828e-04V |
| `vbr1_l2_comparator_measurement_flow` | L2 | core | D3 | Comparator and Decision Circuits | Single-ramp comparator offset measurement flow | 2 | counted | pass/pass | wave 2/2, mean<=0, worst<=0, abs<=0V |
| `vbr1_l2_complete_calibration_loop` | L2 | core | D3 | Calibration, DEM, and Control | Complete calibration loop | 2 | counted | pass/pass | wave 2/2, mean<=1.124e-05, worst<=3.713e-05, abs<=4.805e-05V |
| `vbr1_l2_converter_front_end` | L2 | core | D3 | Sampling and Analog Memory | Converter front-end | 2 | counted | pass/pass | wave 2/2, mean<=1.644e-06, worst<=6.909e-06, abs<=1.758e-04V |
| `vbr1_l2_converter_static_linearity_measurement_flow` | L2 | core | D3 | Data Converter Models | Converter static linearity measurement flow | 2 | counted | pass/pass | wave 2/2, mean<=4.190e-07, worst<=1.459e-06, abs<=1.586e-05V |
| `vbr1_l2_cppll_tracking_and_frequency_step_reacquire_flow` | L2 | core | D3 | PLL Clock and Timing Systems | CPPLL tracking and frequency-step reacquire flow | 3 | counted | pass/pass | wave 1/3, mean<=8.260e-06, worst<=2.541e-05, abs<=1.675e-04V; task metrics 2 forms |
| `vbr1_l2_flash_adc_mini_array` | L2 | core | D3 | Data Converter Models | Flash ADC mini-array | 2 | counted | pass/pass | wave 2/2, mean<=2.450e-17, worst<=2.940e-16, abs<=2.887e-15V |
| `vbr1_l2_gain_extraction_convergence_measurement_flow` | L2 | support | D3 | Measurement Instrumentation Flows | Dithered differential gain extraction flow | 2 | not counted | pass/pass | gain delta<=0.0208 |
| `vbr1_l2_iq_downconversion_chain` | L2 | core | D3 | RF and AFE Behavioral Macromodels | I/Q downconversion chain | 2 | counted | pass/pass | wave 2/2, mean<=1.020e-05, worst<=1.792e-05, abs<=1.406e-04V |
| `vbr1_l2_ldo_load_step_recovery_flow` | L2 | core | D3 | Bias Reference and Power Management | LDO load-step recovery flow | 2 | counted | pass/pass | wave 2/2, mean<=1.135e-06, worst<=5.674e-06, abs<=1.204e-05V |
| `vbr1_l2_measurement_flow` | L2 | support | D3 | Measurement Instrumentation Flows | Measurement flow | 2 | not counted | pass/pass | wave 2/2, mean<=7.172e-07, worst<=1.434e-06, abs<=1.409e-05V |
| `vbr1_l2_pipeline_adc_chain` | L2 | core | D3 | Data Converter Models | Pipeline ADC residue chain | 2 | counted | pass/pass | wave 2/2, mean<=1.273e-06, worst<=1.484e-05, abs<=1.969e-04V |
| `vbr1_l2_programmable_stimulus_sequencer` | L2 | support | D3 | Stimulus and Source Generators | Programmable stimulus sequencer | 2 | not counted | pass/pass | wave 2/2, mean<=0.0062, worst<=0.0333, abs<=0.304V |
| `vbr1_l2_reference_startup_enable_flow` | L2 | core | D3 | Bias Reference and Power Management | Reference startup/enable flow | 2 | counted | pass/pass | wave 2/2, mean<=2.501e-06, worst<=6.996e-06, abs<=1.125e-04V |
| `vbr1_l2_weighted_sar_adc_dac_loop` | L2 | core | D3 | Data Converter Models | Weighted SAR ADC/DAC loop | 2 | counted | pass/pass | wave 2/2, mean<=0.00779, worst<=0.148, abs<=0.896V |

## Exports

- Entry CSV: `benchmark-vabench-release-v1/reports/benchmark_overview_entries.csv`
- Form CSV: `benchmark-vabench-release-v1/reports/benchmark_overview_forms.csv`
- Category CSV: `benchmark-vabench-release-v1/reports/benchmark_overview_categories.csv`

## Claim Boundary

- This overview is a derived navigation/reporting table; VABENCH_300_MANIFEST.json is the benchmark management manifest.
- Current full-300 backend evidence is grounded by the explicit results/*/summary.json files listed in backend_coverage.
- Do not state bit-exact EVAS/Spectre equality; state behavior/spec pass plus tolerance-gated waveform or task-metric parity.
- Negative candidates are static-shape audited partial-pass assets unless a separate full-checker validation report is produced.
- All 29 fresh-certified v1.1 rows are score-denominator admitted; support-suite exclusions still apply to paper-facing scores.
