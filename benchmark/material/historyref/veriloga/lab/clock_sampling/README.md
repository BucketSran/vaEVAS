# 课题组工程资料：时钟、采样与数据对齐

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [bus11_edge_sampler_csv.va](bus11_edge_sampler_csv.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-bus11_edge_sampler_csv) | 按指定时钟边沿采样十一通道电压，并可记录 CSV。 | `` single_edge_sampler(clk, vin, vout) `` | `` direction = 1 from [-1:1] exclude 0 ``；`` real vdd = 1.2 ``；`` real tr = 100p ``<br>部分 fwrite 在 file_io 条件外；使用文件输出前需检查原实现。 |
| [clocked_mux_8channel.va](clocked_mux_8channel.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-clocked_mux_8channel) | 随时钟轮询八路输入，并输出当前通道编号。 | `` IDEAL_CLKMUX(out, clk, in0, in1, in2, in3, in4, in5, in6, in7, count_x) `` | 原名 DAC_4bit_restore_8channel，实际 module 为 IDEAL_CLKMUX。 |
| [flash_code_pipeline_alignment.va](flash_code_pipeline_alignment.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-flash_code_pipeline_alignment) | 统计八路比较结果并通过寄存级延迟后输出四位码。 | `` FLASH_DATA_ALIGN_V2(dither_out, dout, clk, din, dither_in) `` | `` real Vth = 0.45 ``<br>原声明的 dither_out 未被驱动，部分寄存状态未显式初始化。 |
| [mux4_falling_edge.va](mux4_falling_edge.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-mux4_falling_edge) | 在时钟下降沿按两位选择码采样四路输入之一。 | `` MUX4T1(DSEL,DIN,DOUT,CLKS) `` | `` real Vth = 0.45 ``<br>输出带固定皮秒级过渡。 |
| [one_shot_lab_copy.va](one_shot_lab_copy.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-one_shot_lab_copy) | 检测输入上升沿后输出指定宽度的单稳脉冲。 | `` single_shot(vin, vout) `` | `` real pulse_width = 10n from (0:inf) ``；`` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``<br>脉冲宽度、延迟和边沿时间可配置。 |
| [pfd_upbar_down.va](pfd_upbar_down.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-pfd_upbar_down) | 双输入鉴相鉴频，输出反相 UP 和正相 DOWN。 | `` L2_PFD(D, UB, GND, VDD, A, B) `` | 输入门限固定 0.5 V，内部复位间隔 10 ps。 |
| [pfd_with_reset_pulse.va](pfd_with_reset_pulse.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-pfd_with_reset_pulse) | 比较两路上升沿先后，生成 UP/DN，并带短暂共同置高复位阶段。 | `` PFD_Tdomain(IN1,IN2,UP,DN,VDD,GND) `` | `` real ttol=5f from [0:inf) ``；`` real td=0 from [0:inf) ``；`` real tt=10f from (0:inf) ``<br>ton 控制复位脉宽；参考电平来自 VDD/GND。 |
| [pll_delay_path_mux.va](pll_delay_path_mux.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-pll_delay_path_mux) | 按数值控制选择三条延迟路径，供 PLL 路径切换使用。 | `` MUX4(delay0,delay1,delay2,ctrl,Vout,GND) `` | 控制值 0 和 2 均选择 delay1；并非四个独立数据输入。 |
| [sample_hold_lab_copy.va](sample_hold_lab_copy.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-sample_hold_lab_copy) | 时钟上升沿采样并保持输入电压。 | `` sah_ideal(vin, vout, vclk) `` | `` real vtrans_clk = 2.5 ``<br>输出直接赋电压，未显式加入过渡时间。 |
| [two_channel_interleaved_alignment.va](two_channel_interleaved_alignment.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-two_channel_interleaved_alignment) | 时钟上升沿取 DIN1、下降沿取 DIN2，交织输出两个通道的数据。 | `` ideal_PIPE_10B_TI_ALIGN(input electrical DIN1, input electrical DIN2, input electrical CLK_ALIGN, output electrical DOUT) `` | `` real gnd=0, vdd=0.9 ``；`` real vth = 0.45 ``<br>输出直接赋电压，未加入平滑过渡。 |
| [voltage_programmed_clock_divider.va](voltage_programmed_clock_divider.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-voltage_programmed_clock_divider) | 计数输入上升沿，按 divctrl 电压给出的计数值周期回零并输出脉冲。 | `` divider(in,out,divctrl) `` | `` real Vlo=0, Vhi=1.2 ``<br>输出不是固定 50% 占空比；原 module 名为 divider。 |
| [zoom_sampling_clock_1600ns.va](zoom_sampling_clock_1600ns.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-zoom_sampling_clock_1600ns) | 产生 1600 ns 周期的采样、噪声消除、复位和转换控制。 | `` CLOCK_VA_SAMPLE_1600n(RST, S, NC, RES, CONV) `` | `` real vdd=1.1 ``；`` real init_delay=0n ``；`` real trise=0.1n ``<br>保留原始定时器及未使用参数，不能按名称推定所有参数均生效。 |
| [zoom_sampling_clock_1800ns.va](zoom_sampling_clock_1800ns.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-zoom_sampling_clock_1800ns) | 产生 1800 ns 周期的采样、自零、噪声消除和转换控制。 | `` CLOCK_VA_SAMPLE_1800n(RST, S, SS, NC_AZ,NC,CONV) `` | `` real vdd=1.1 ``；`` real init_delay=0n ``；`` real trise=0.02n ``<br>每周期默认三组采样时序，接口不同于 1600 ns 版本。 |
| [zoom_sar_multiphase_clock.va](zoom_sar_multiphase_clock.va)<br>[来源](../../SOURCES.md#lab-clock_sampling-zoom_sar_multiphase_clock) | 产生复位、采样、SAR、积分和 ZOOM 等多相控制脉冲。 | `` CLOCK_VA(RST, S, SAR, RES, INT,CLK_SAR,ZOOM,CLK_ZOOM, RST_ZOOM) `` | `` real vdd=1.1 ``；`` real init_delay=5n ``；`` real trise=0.1n ``<br>来自 ZOOM/NSSAR 工程；大量时序参数相互配套。 |
