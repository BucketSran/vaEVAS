# Bugfix Companion: vbr1_l1_digital_phase_accumulator_with_modulo_wrap

- Fixed source: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_digital_phase_accumulator_with_modulo_wrap/forms/dut/gold/phase_accumulator_timer_wrap_ref.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_digital_phase_accumulator_with_modulo_wrap/forms/dut/gold/tb_phase_accumulator_timer_wrap_ref.scs`
- Bug: The buggy accumulator omits modulo wrap after the phase reaches one cycle.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
