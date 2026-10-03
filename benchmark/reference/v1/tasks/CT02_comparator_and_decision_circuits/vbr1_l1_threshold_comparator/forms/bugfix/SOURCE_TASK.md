# Bugfix Companion: vbr1_l1_threshold_comparator

- Fixed source: `benchmark-vabench-release-v1/tasks/CT02_comparator_and_decision_circuits/vbr1_l1_threshold_comparator/forms/dut/gold/comparator.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT02_comparator_and_decision_circuits/vbr1_l1_threshold_comparator/forms/dut/gold/tb_comparator_ref.scs`
- Bug: The buggy comparator drives the output with reversed polarity.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
