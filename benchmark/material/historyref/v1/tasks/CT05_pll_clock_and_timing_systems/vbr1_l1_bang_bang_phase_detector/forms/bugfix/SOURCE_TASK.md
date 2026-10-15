# Bugfix Companion: vbr1_l1_bang_bang_phase_detector

- Fixed source: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_bang_bang_phase_detector/forms/dut/gold/bbpd_ref.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_bang_bang_phase_detector/forms/dut/gold/tb_bbpd_ref.scs`
- Bug: The buggy bang-bang phase detector swaps the UP and DOWN output drives.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
