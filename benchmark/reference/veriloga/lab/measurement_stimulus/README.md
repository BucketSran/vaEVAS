# 课题组工程资料：测量与激励

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [constant_code_source_7bit.va](constant_code_source_7bit.va)<br>[来源](../../SOURCES.md#lab-measurement_stimulus-constant_code_source_7bit) | 把 CTRL 参数展开为七路静态电平码；用于编码器或 DAC 激励。 | `` V_ENCODER_7B(D) `` | `` CTRL = 64 ``<br>输出逻辑电平为 0/1 V。 |
| [crossing_pulse_detector_lab_copy.va](crossing_pulse_detector_lab_copy.va)<br>[来源](../../SOURCES.md#lab-measurement_stimulus-crossing_pulse_detector_lab_copy) | 输入跨越阈值时产生固定宽度脉冲，用于事件观察。 | `` crossing_detector(sigin,sigout) `` | `` real pulse_width = 1u from (0:inf) ``；`` real sigcrossing = 0 ``；`` real vlogic_high = 5 ``<br>同时响应上升和下降穿越；保留 instrument_module 属性。 |
| [dac7_clocked_code_stimulus.va](dac7_clocked_code_stimulus.va)<br>[来源](../../SOURCES.md#lab-measurement_stimulus-dac7_clocked_code_stimulus) | 用时钟推进计数并驱动七路 DAC 测试激励电平。 | `` DAC7B_TB_VA(CLKS,DIN) `` | `` real Vlo=0 ``；`` real Vhi=5 ``；`` real Vth = 0.75 ``<br>原始位运算优先级和计数范围需按实际用例检查，未宣称遍历所有码。 |
| [differential_edge_time_detector.va](differential_edge_time_detector.va)<br>[来源](../../SOURCES.md#lab-measurement_stimulus-differential_edge_time_detector) | 捕获两路首个上升沿的时间差，转换为限幅电压输出。 | `` ideal_TIME_DIFF_DETECTOR(input electrical clk, input electrical vinp, input electrical vinn, output electrical vout) `` | `` real vdd = 0.9 ``；`` real vth_clk = 0.9/2 ``；`` real vth_in = 0.9/2 ``<br>在下个 clk 上升沿读出；缺失边沿时没有独立的有效性输出。 |
| [encoder_thermometer_stimulus.va](encoder_thermometer_stimulus.va)<br>[来源](../../SOURCES.md#lab-measurement_stimulus-encoder_thermometer_stimulus) | 逐周期置高下一条输出，产生十六路累积温度计激励及计数观察量。 | `` VA_encoder_test(CK, D, SUM) `` | 只递增到十六，没有循环或复位端口，原数组未显式全部初始化。 |
| [flash8_population_readout.va](flash8_population_readout.va)<br>[来源](../../SOURCES.md#lab-measurement_stimulus-flash8_population_readout) | 统计八路比较器高电平数，输出以中点为零的电压。 | `` TB_flash(DIN,DOUT) `` | `` real vth=0.45 ``；`` real GAIN=4 ``<br>使用固定 0.9 V 标度；原 GAIN 参数未参与输出表达式。 |
