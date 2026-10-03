# 课题组工程资料：模拟信号处理

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [analog_mux_lab_copy.va](analog_mux_lab_copy.va)<br>[来源](../../SOURCES.md#lab-analog-analog_mux_lab_copy) | 电压选择控制的二选一模拟复用器。 | `` analog_mux(vin1, vin2, vsel, vout) `` | `` real vth = 2.5 ``<br>从课题组 ahdlLib 副本恢复；与本次官方安装文件不同，不据此认定原创。 |
| [diffamp_clamped_0_to_0p9v.va](diffamp_clamped_0_to_0p9v.va)<br>[来源](../../SOURCES.md#lab-analog-diffamp_clamped_0_to_0p9v) | 差分输入放大并将输出限制在 0 至 0.9 V。 | `` diffamp(sigin_p, sigin_n, sigout) `` | `` real gain = 1 ``；`` real sigin_offset = 0 ``；`` real sigout_offset = 0.45 ``<br>默认输出偏置 0.45 V；限幅值固定在实现中。 |
| [differential_polynomial_vcvs_high_order_defaults.va](differential_polynomial_vcvs_high_order_defaults.va)<br>[来源](../../SOURCES.md#lab-analog-differential_polynomial_vcvs_high_order_defaults) | 差分多项式电压放大与限幅，默认带五阶和七阶非线性。 | `` LI_VCVS_NLIN(inp, inn, outp, outn) `` | `` Vcmo = 1.1 from (0:inf) ``；`` a1 = 1 ``；`` a2 = 0 ``<br>默认 a5=0.00004、a7=0.00002；其他结构与 linear_defaults 版本一致。 |
| [differential_polynomial_vcvs_linear_defaults.va](differential_polynomial_vcvs_linear_defaults.va)<br>[来源](../../SOURCES.md#lab-analog-differential_polynomial_vcvs_linear_defaults) | 差分多项式电压放大与限幅；用于可配置非线性驱动建模。 | `` LI_VCVS_NLIN(inp, inn, outp, outn) `` | `` Vcmo = 1.1 from (0:inf) ``；`` a1 = 1 ``；`` a2 = 0 ``<br>默认 a1=1，其余高次系数为零，输出共模 1.1 V。 |
| [differential_unity_buffer.va](differential_unity_buffer.va)<br>[来源](../../SOURCES.md#lab-analog-differential_unity_buffer) | 分别复制正负输入电压；用于理想差分隔离或连接替代。 | `` TOOL_buffer(VINP,VINN,VOUTP,VOUTN) `` | 无负载、带宽或限幅模型。 |
| [supply_headroom_limiter.va](supply_headroom_limiter.va)<br>[来源](../../SOURCES.md#lab-analog-supply_headroom_limiter) | 按供电与上下裕量限制输入电压。 | `` Limiter(vdd,vss,vin,vmax,vmin,vout) `` | 上限为 vdd−vmax，下限为 vss+vmin。 |
| [three_way_analog_mux_lab_copy.va](three_way_analog_mux_lab_copy.va)<br>[来源](../../SOURCES.md#lab-analog-three_way_analog_mux_lab_copy) | 按差分控制量的两个门限选择三路模拟输入之一。 | `` multiplexer(sigin1, sigin2, sigin3, cntrlp, cntrlm, sigout) `` | `` real sigth_high = 1 ``；`` real sigth_low = -1 ``<br>输出使用 slew；来自课题组 ahdlLib 副本。 |
| [voltage_ratio_divider_lab_copy.va](voltage_ratio_divider_lab_copy.va)<br>[来源](../../SOURCES.md#lab-analog-voltage_ratio_divider_lab_copy) | 计算两路电压之比，并限制分母最小绝对值。 | `` divider(signumer, sigdenom, sigout) `` | `` real gain = 1 ``；`` real min_sigdenom = 1.0e-9 from (0:inf) ``<br>这是数学除法器，不是时钟分频器。 |
