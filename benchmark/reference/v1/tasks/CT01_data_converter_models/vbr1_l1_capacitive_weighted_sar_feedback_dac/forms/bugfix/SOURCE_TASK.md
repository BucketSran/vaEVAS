# Bugfix Companion: vbr1_l1_capacitive_weighted_sar_feedback_dac

- Fixed source: `benchmark-vabench-release-v1/tasks/CT01_data_converter_models/vbr1_l1_capacitive_weighted_sar_feedback_dac/forms/dut/gold/cdac_cal.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT01_data_converter_models/vbr1_l1_capacitive_weighted_sar_feedback_dac/forms/dut/gold/tb_cdac_cal_ref.scs`
- Bug: The buggy feedback DAC ignores the calibration bits when computing the differential output.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
