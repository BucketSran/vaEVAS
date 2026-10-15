# CT08 Stimulus and Source Generators

SUP02 covers reusable voltage-domain stimulus/source models whose output
waveforms are themselves the behavioral object under test. It should not absorb
generic digital logic; discrete-state sources are kept only when they produce a
public voltage-coded stimulus useful for mixed-signal validation.

| ID | Entry | Level | Circuit role | Why kept | Primary behavior checks |
| --- | --- | --- | --- | --- | --- |
| CT08-01 | `vbr1_l1_burst_clock_source` | L1 | Gated burst clock source with reset-visible output behavior. | Covers clock stimulus generation with burst duty-cycle structure. | `clk_out_present`, `clk_out_duty_cycle_is_burst` |
| CT08-02 | `vbr1_l1_dither_or_noise_like_deterministic_source` | L1 | Deterministic analog-valued perturbation source added to an input waveform. | Distinct from PRBS: the observable is a nontrivial analog dither/noise-like waveform. | `noise_is_nontrivial`, `noise_std_in_range` |
| CT08-03 | `vbr1_l1_lfsr_prbs_generator` | L1 | Voltage-coded PRBS/LFSR source for repeatable dynamic stimulus. | Distinct from analog dither: the contract is deterministic state progression and transitions. | `prbs7_sequence_advances`, `serial_output_has_transitions`, `parallel_state_bus_updates` |
| CT08-04 | `vbr1_l1_ramp_or_step_source` | L1 | Periodic phase-ramp source with guard pulse generation. | Covers ramp/wrap stimulus and bounded-step guard behavior. | `periodic_phase_ramp_wraps`, `guard_pulse_repeats_each_period`, `guard_pulse_width_fraction` |
| CT08-05 | `vbr1_l1_sine_periodic_voltage_source` | L1 | Parameterized sinusoidal/multitone voltage source. | Covers continuous periodic waveform generation with public sampled waveform checks. | `multitone_waveform_matches_public_samples` |
| CT08-06 | `vbr1_l2_programmable_stimulus_sequencer` | L2 | Programmable stimulus sequencer combining ramp, swept/chirp sine, and gated burst/PRBS modes. | Kept as a composed stimulus schedule rather than another single waveform source. | `ramp_segment_monotonic`, `swept_chirp_segment_frequency_increases`, `burst_prbs_gate_schedule`, `mode_switch_continuity` |

Audit rule: SUP02 should justify each retained entry as a source waveform or a
stimulus-driven flow. Pure digital state machines with no source role should be
placed in a more relevant category or removed from paper-facing coverage.
