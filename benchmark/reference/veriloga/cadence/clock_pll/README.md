# Cadence 安装库模型：时钟与锁相环

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [charge_pump__ic618hotfix4.va](charge_pump__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-charge_pump__ic618hotfix4) | 按增减控制信号向输出节点注入或抽取电流。 | `` charge_pump(siginc, sigdec, vout, vsrc) `` | IC618Hotfix4<br>`` real iamp=0.5m from [0:inf) ``；`` real vtrans = 2.5 ``；`` real tdel=0 from [0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [charge_pump__icadvm201.va](charge_pump__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-charge_pump__icadvm201) | 按增减控制信号向输出节点注入或抽取电流。 | `` charge_pump(siginc, sigdec, vout, vsrc) `` | ICADVM201<br>`` real iamp=0.5m from [0:inf) ``；`` real vtrans = 2.5 ``；`` real tdel=0 from [0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [dig_pll.va](dig_pll.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-dig_pll) | 由鉴相、电荷泵、滤波和振荡器组成的数字电平 PLL 示例。 | `` dig_pll(vin,vout,gnd) `` | IC618Hotfix4 / ICADVM201<br>`` real pump_iamp = 1m from (0:inf) ``；`` real vco_cen_freq = 1M from (0:inf) ``；`` real vco_gain = 1M from (0:inf) `` |
| [dig_pll_lpf.va](dig_pll_lpf.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-dig_pll_lpf) | 数字 PLL 使用的环路滤波器。 | `` dig_pll_lpf(in, ref) `` | IC618Hotfix4 / ICADVM201<br>`` real pole_freq = 3M ``；`` real zero_freq = 0.5M ``；`` real r_nom = 10K `` |
| [dig_vco__ic618hotfix4.va](dig_vco__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-dig_vco__ic618hotfix4) | 输入电压控制输出数字时钟频率的振荡器。 | `` dig_vco(vin, vout) `` | IC618Hotfix4<br>`` real center_freq=2.5K ``；`` real vco_gain = 1 ``；`` real vlogic_high = 5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [dig_vco__icadvm201.va](dig_vco__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-dig_vco__icadvm201) | 输入电压控制输出数字时钟频率的振荡器。 | `` dig_vco(vin, vout) `` | ICADVM201<br>`` real center_freq=2.5K ``；`` real vco_gain = 1 ``；`` real vlogic_high = 5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [freq_ph_detector__ic618hotfix4.va](freq_ph_detector__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-freq_ph_detector__ic618hotfix4) | 检测两路信号的相位及频率关系。 | `` freq_ph_detector(vin_if, vin_lo, sigout_inc, sigout_dec) `` | IC618Hotfix4<br>`` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans = 2.5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [freq_ph_detector__icadvm201.va](freq_ph_detector__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-freq_ph_detector__icadvm201) | 检测两路信号的相位及频率关系。 | `` freq_ph_detector(vin_if, vin_lo, sigout_inc, sigout_dec) `` | ICADVM201<br>`` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``；`` real vtrans = 2.5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [phase_detector.va](phase_detector.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-phase_detector) | 检测两路输入的相位关系。 | `` phase_detector(vlocal_osc, vin_rf, vif) `` | IC618Hotfix4 / ICADVM201<br>`` real gain = 1 ``；`` integer pd_type = `chop `` |
| [pll.va](pll.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-pll) | 模拟锁相环组合示例。 | `` pll(vin_rf,vlocal_osc,vout_ph_det,vout) `` | IC618Hotfix4 / ICADVM201<br>`` real vout_filt_bandwidth=130 ``；`` real vco_gain=1K ``；`` real vco_center_freq=2.5K `` |
| [single_shot__ic618hotfix4.va](single_shot__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-single_shot__ic618hotfix4) | 边沿触发的单稳脉冲发生器。 | `` single_shot(vin, vout) `` | IC618Hotfix4<br>`` real pulse_width = 10n from (0:inf) ``；`` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [single_shot__icadvm201.va](single_shot__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-single_shot__icadvm201) | 边沿触发的单稳脉冲发生器。 | `` single_shot(vin, vout) `` | ICADVM201<br>`` real pulse_width = 10n from (0:inf) ``；`` real vlogic_high = 5 ``；`` real vlogic_low = 0 ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [vco.va](vco.va)<br>[来源](../../SOURCES.md#cadence-clock_pll-vco) | 电压控制正弦振荡器。 | `` vco(vin, vout) `` | IC618Hotfix4 / ICADVM201<br>`` real amp = 1 ``；`` real center_freq = 1K ``；`` real vco_gain = 1K `` |
