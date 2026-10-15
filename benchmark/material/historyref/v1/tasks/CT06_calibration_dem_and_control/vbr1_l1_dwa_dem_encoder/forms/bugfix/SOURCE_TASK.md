# Bugfix Companion: vbr1_l1_dwa_dem_encoder

- Fixed source: `benchmark-vabench-release-v1/tasks/CT06_calibration_dem_and_control/vbr1_l1_dwa_dem_encoder/forms/dut/gold/dwa_ptr_gen.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT06_calibration_dem_and_control/vbr1_l1_dwa_dem_encoder/forms/dut/gold/tb_dwa_ptr_gen_ref.scs`
- Companion dependency: `benchmark-vabench-release-v1/tasks/CT06_calibration_dem_and_control/vbr1_l1_dwa_dem_encoder/forms/dut/gold/v2b_4b.va`
- Bug: The buggy DWA/DEM encoder computes the cell mask but never advances the rotating pointer.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
