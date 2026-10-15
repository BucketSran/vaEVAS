# Cadence 安装库模型：数学运算

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [absolute_value.va](absolute_value.va)<br>[来源](../../SOURCES.md#cadence-math-absolute_value) | 取输入电压绝对值，用于整流或幅值处理。 | `` absolute_value(sigin, sigout) `` | IC618Hotfix4 / ICADVM201 |
| [adder.va](adder.va)<br>[来源](../../SOURCES.md#cadence-math-adder) | 对两路输入按各自增益加权求和。 | `` adder(sigin1, sigin2, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real k1 = 1 ``；`` real k2 = 1 `` |
| [adder_4.va](adder_4.va)<br>[来源](../../SOURCES.md#cadence-math-adder_4) | 对四路输入按各自增益加权求和。 | `` adder_4(sigin1, sigin2, sigin3, sigin4, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain1 = 1 ``；`` real gain2 = 1 ``；`` real gain3 = 1 `` |
| [cube.va](cube.va)<br>[来源](../../SOURCES.md#cadence-math-cube) | 计算输入的三次方。 | `` cube(sigin, sigout) `` | IC618Hotfix4 / ICADVM201 |
| [cube_root.va](cube_root.va)<br>[来源](../../SOURCES.md#cadence-math-cube_root) | 计算立方根，带小量修正参数。 | `` cube_root(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real epsilon = 1e-6 `` |
| [divider.va](divider.va)<br>[来源](../../SOURCES.md#cadence-math-divider) | 计算两路电压之比，限制分母最小绝对值。 | `` divider(signumer, sigdenom, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain = 1 ``；`` real min_sigdenom = 1.0e-9 from (0:inf) `` |
| [exponential.va](exponential.va)<br>[来源](../../SOURCES.md#cadence-math-exponential) | 计算输入的指数函数。 | `` exponential(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real max_sigin = 180 `` |
| [multiplier.va](multiplier.va)<br>[来源](../../SOURCES.md#cadence-math-multiplier) | 对两个输入相乘并施加增益。 | `` multiplier(sigin1, sigin2, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain = 1 `` |
| [natural_log.va](natural_log.va)<br>[来源](../../SOURCES.md#cadence-math-natural_log) | 计算输入的自然对数。 | `` natural_log(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real min_sigin = 1.0e-6 `` |
| [polynomial.va](polynomial.va)<br>[来源](../../SOURCES.md#cadence-math-polynomial) | 三阶多项式传输函数。 | `` polynomial(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real p0 = 1.0 ``；`` real p1 = 1.0 ``；`` real p2 = 1.0 `` |
| [power_of.va](power_of.va)<br>[来源](../../SOURCES.md#cadence-math-power_of) | 计算可配置幂函数。 | `` power_of(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real exponent = 1 ``；`` real epsilon = 1e-6 `` |
| [reciprocal.va](reciprocal.va)<br>[来源](../../SOURCES.md#cadence-math-reciprocal) | 计算输入的倒数。 | `` reciprocal(sigin, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain = 1.0 ``；`` real min_sigdenom = 1.0e-9 from (0:inf) `` |
| [signum.va](signum.va)<br>[来源](../../SOURCES.md#cadence-math-signum) | 输出输入的正负符号。 | `` signum(sigin, sigout) `` | IC618Hotfix4 / ICADVM201 |
| [square.va](square.va)<br>[来源](../../SOURCES.md#cadence-math-square) | 计算输入平方。 | `` square(sigin, sigout) `` | IC618Hotfix4 / ICADVM201 |
| [square_root.va](square_root.va)<br>[来源](../../SOURCES.md#cadence-math-square_root) | 计算输入平方根。 | `` square_root(sigin, sigout) `` | IC618Hotfix4 / ICADVM201 |
| [subtractor.va](subtractor.va)<br>[来源](../../SOURCES.md#cadence-math-subtractor) | 计算两路输入之差。 | `` subtractor(sigin_p, sigin_n, sigout) `` | IC618Hotfix4 / ICADVM201 |
| [subtractor_4.va](subtractor_4.va)<br>[来源](../../SOURCES.md#cadence-math-subtractor_4) | 带权重的四输入减法组合。 | `` subtractor_4(sigin1, sigin2, sigin3, sigin4, sigout) `` | IC618Hotfix4 / ICADVM201<br>`` real gain1 = 1.0 ``；`` real gain2 = 1.0 ``；`` real gain3 = 1.0 `` |
