# 比较器传播延时与过驱动来源与边界

这是根据工程需求原创的动态辨识题。数据身份是 `behavioral_synthetic`，
不声称器件电路仿真、silicon测量或厂商模型输出。
一手工程参考为 [比较器传播延时与过驱动](https://www.analog.com/en/resources/technical-articles/parameters-that-affect-comparator-propagation-delay-measurements.html)，只支持架构与指标的工程意义。
资料支持overdrive、slew和测量条件影响传播延时。本题是原创strobed差分决策接口，未宣称复刻文档中的continuous-time器件。

作者生成器与独立目标在 `experiments/benchmark_first_batch/identification/`。
公开与隐藏部分按完整实验划分，同一个固定系统只改变题面允许的刺激。
参考解只从公开观测估计可行参数，不使用终评系数。
checker逐条检查局部样点、时序或性能指标，不运行参考解生成正确答案。

语义负例包括固定延时、忽略正负不对称、复位后迟到决策和错误dispersion。编译错误不计这些负例。
当前是 Spectre 扩展集候选。Python行级检查不等于实际VA校准，
Spectre、Agentic和开源复现证据分别记录。
