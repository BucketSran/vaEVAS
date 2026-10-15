# Cadence 安装库模型：数据转换与编码

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [adc_8bit.va](adc_8bit.va)<br>[来源](../../SOURCES.md#cadence-data_converters-adc_8bit) | 带失配参数的八位时钟 ADC 行为模型。 | `` adc_8bit(vd7,vd6,vd5,vd4,vd3,vd2,vd1,vd0,vin,vclk) `` | IC618Hotfix4 / ICADVM201<br>`` real trise = 0 from [0:inf) ``；`` real tfall = 0 from [0:inf) ``；`` real tdel = 0 from [0:inf) `` |
| [adc_8bit_ideal.va](adc_8bit_ideal.va)<br>[来源](../../SOURCES.md#cadence-data_converters-adc_8bit_ideal) | 理想八位时钟 ADC，将输入电压转换为八路电平码。 | `` adc_8bit_ideal(vd7, vd6, vd5, vd4, vd3, vd2, vd1, vd0, vin, vclk) `` | IC618Hotfix4 / ICADVM201<br>`` real trise = 0 from [0:inf) ``；`` real tfall = 0 from [0:inf) ``；`` real tdel = 0 from [0:inf) `` |
| [dac_8bit.va](dac_8bit.va)<br>[来源](../../SOURCES.md#cadence-data_converters-dac_8bit) | 带失配参数的八位电压输出 DAC。 | `` dac_8bit(vd7, vd6, vd5, vd4, vd3, vd2, vd1, vd0, vout) `` | IC618Hotfix4 / ICADVM201<br>`` real vref=1 from [0:inf) ``；`` real mismatch_fact=0 from [0:inf) ``；`` real trise=1u from (0:inf) `` |
| [dac_8bit_ideal.va](dac_8bit_ideal.va)<br>[来源](../../SOURCES.md#cadence-data_converters-dac_8bit_ideal) | 理想八位电压输出 DAC。 | `` dac_8bit_ideal(vd7, vd6, vd5, vd4, vd3, vd2, vd1, vd0, vout) `` | IC618Hotfix4 / ICADVM201<br>`` real vref = 1 from [0:inf) ``；`` real trise = 0 from [0:inf) ``；`` real tfall = 0 from [0:inf) `` |
| [decimator__ic618hotfix4.va](decimator__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-data_converters-decimator__ic618hotfix4) | 对过采样位流累积并降采样。 | `` decimator(vin, vout, vclk) `` | IC618Hotfix4<br>`` integer N=64 from [0:inf) ``；`` real vtrans_clk=2.5 ``；`` real tdel = 0 from [0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [decimator__icadvm201.va](decimator__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-data_converters-decimator__icadvm201) | 对过采样位流累积并降采样。 | `` decimator(vin, vout, vclk) `` | ICADVM201<br>`` integer N=64 from [0:inf) ``；`` real vtrans_clk=2.5 ``；`` real tdel = 0 from [0:inf) ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [quantizer.va](quantizer.va)<br>[来源](../../SOURCES.md#cadence-data_converters-quantizer) | 按设定分辨率量化输入，输出离散模拟电平。 | `` quantizer(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` integer nlevel = 2 from [2:inf) ``；`` integer round=1 ``；`` real sigout_high = 1 `` |
| [sah_ideal__ic618hotfix4.va](sah_ideal__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-data_converters-sah_ideal__ic618hotfix4) | 时钟触发的理想采样保持器。 | `` sah_ideal(vin, vout, vclk) `` | IC618Hotfix4<br>`` real vtrans_clk = 2.5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [sah_ideal__icadvm201.va](sah_ideal__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-data_converters-sah_ideal__icadvm201) | 时钟触发的理想采样保持器。 | `` sah_ideal(vin, vout, vclk) `` | ICADVM201<br>`` real vtrans_clk = 2.5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
| [sigmadelta_1storder__ic618hotfix4.va](sigmadelta_1storder__ic618hotfix4.va)<br>[来源](../../SOURCES.md#cadence-data_converters-sigmadelta_1storder__ic618hotfix4) | 一阶 Sigma–Delta 模数转换组合模型。 | `` sigmadelta_1storder(vin, vclk, vout) `` | IC618Hotfix4<br>`` real vth=0.0 ``；`` real vout_high=5.0 ``；`` real vtrans_clk=2.5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。<br>含 instrument_module 属性。 |
| [sigmadelta_1storder__icadvm201.va](sigmadelta_1storder__icadvm201.va)<br>[来源](../../SOURCES.md#cadence-data_converters-sigmadelta_1storder__icadvm201) | 一阶 Sigma–Delta 模数转换组合模型。 | `` sigmadelta_1storder(vin, vclk, vout) `` | ICADVM201<br>`` real vth=0.0 ``；`` real vout_high=5.0 ``；`` real vtrans_clk=2.5 ``<br>保留安装版本差异；同名 module 的版本应择一使用。 |
