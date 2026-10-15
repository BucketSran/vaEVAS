# Bugfix Companion: vbr1_l1_lfsr_prbs_generator

- Fixed source: `benchmark-vabench-release-v1/tasks/SUP02_stimulus_and_source_generators/vbr1_l1_lfsr_prbs_generator/forms/dut/gold/prbs7_ref.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/SUP02_stimulus_and_source_generators/vbr1_l1_lfsr_prbs_generator/forms/dut/gold/tb_prbs7_ref.scs`
- Bug: The buggy PRBS generator uses the wrong feedback tap and shortens the intended sequence.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
