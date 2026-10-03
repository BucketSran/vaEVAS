# Bugfix Companion: vbr1_l1_vco_phase_integrator

- Fixed source: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_vco_phase_integrator/forms/dut/gold/vco_phase_integrator.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_vco_phase_integrator/forms/dut/gold/tb_vco_phase_integrator_ref.scs`
- Bug: The buggy VCO phase integrator wraps phase but never toggles the clock output on wrap.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
