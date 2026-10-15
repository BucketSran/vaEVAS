# Bugfix Companion: vbr1_l1_clock_divider

- Fixed source: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_clock_divider/forms/dut/gold/clk_divider_ref.va`
- Reference testbench: `benchmark-vabench-release-v1/tasks/CT05_pll_clock_and_timing_systems/vbr1_l1_clock_divider/forms/dut/gold/tb_clk_divider_ref.scs`
- Bug: The buggy clock divider uses the low segment length for both halves of an odd divide ratio.
- EVAS/Spectre status: pass in release dual evidence

This bugfix form was created only where a single-cause badcase
could be reconstructed from existing release gold. It is not
imported as historical certification evidence.
