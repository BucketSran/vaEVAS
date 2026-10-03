# vaBench Release Tasks By Circuit Type

This directory groups release benchmark entries by the circuit-type IDs used for
manual prompt and checker audit. Each `vbr1_*` entry remains a self-contained
release benchmark with `release_entry.json` and per-form `forms/*` assets.

| ID | Directory | Circuit type | Entries |
| --- | --- | --- | ---: |
| CT01 | `CT01_data_converter_models` | Data Converter Models | 18 |
| CT02 | `CT02_comparator_and_decision_circuits` | Comparator and Decision Circuits | 8 |
| CT03 | `CT03_sampling_and_analog_memory` | Sampling and Analog Memory | 4 |
| CT04 | `CT04_baseband_signal_conditioning` | Baseband Signal Conditioning | 7 |
| CT05 | `CT05_pll_clock_and_timing_systems` | PLL Clock and Timing Systems | 13 |
| CT06 | `CT06_calibration_dem_and_control` | Calibration, DEM, and Control | 7 |
| CT07 | `SUP01_measurement_instrumentation_flows` | Measurement Instrumentation Flows | 7 |
| CT08 | `SUP02_stimulus_and_source_generators` | Stimulus and Source Generators | 6 |

Use the category folders for human review. Machine-readable manifests and
report paths use the same canonical category layout.
