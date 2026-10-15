# Bugfix Companion: vbr1_l1_clocked_adc_quantizer

- Fixed source: `benchmark-vabench-release-v1/tasks/CT01_data_converter_models/vbr1_l1_clocked_adc_quantizer/forms/dut/gold/flash_adc_3b.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT01_data_converter_models/vbr1_l1_clocked_adc_quantizer/forms/dut/gold/tb_flash_adc_3b_ref.scs`
- Bug: The buggy quantizer saturates at code 6 and never emits the top ADC code.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
