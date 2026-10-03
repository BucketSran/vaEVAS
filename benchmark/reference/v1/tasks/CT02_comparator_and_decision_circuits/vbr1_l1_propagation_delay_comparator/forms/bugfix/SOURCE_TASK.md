# Bugfix Companion: vbr1_l1_propagation_delay_comparator

- Fixed source: `benchmark-vabench-release-v1/tasks/CT02_comparator_and_decision_circuits/vbr1_l1_propagation_delay_comparator/forms/dut/gold/cmp_delay.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT02_comparator_and_decision_circuits/vbr1_l1_propagation_delay_comparator/forms/dut/gold/tb_cmp_delay_ref.scs`
- Companion dependency: `benchmark-vabench-release-v1/tasks/CT02_comparator_and_decision_circuits/vbr1_l1_propagation_delay_comparator/forms/dut/gold/edge_interval_timer.va`
- Bug: The buggy propagation-delay comparator removes the input-amplitude dependent regeneration delay.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
