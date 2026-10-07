# ADC驱动级建立时间来源与边界

这是根据工程需求原创的动态辨识题。数据身份是 `behavioral_synthetic`，
不声称器件电路仿真、silicon测量或厂商模型输出。
一手工程参考为 [ADC驱动级建立时间](https://www.analog.com/media/en/reference-design-documentation/reference-designs/CN0269.pdf)，只支持架构与指标的工程意义。
本题只模拟固定条件下的电压闭环级。资料中真实ADC负载、RC和电流设计没有转移为候选要求。建立时间须进入且保持误差带；目标波形和采集时刻误差是独立合同。

作者生成器与独立目标在 `experiments/benchmark_first_batch/identification/`。
公开与隐藏部分按完整实验划分，同一个固定系统只改变题面允许的刺激。
参考解只从公开观测估计可行参数，不使用终评系数。
checker逐条检查局部样点、时序或性能指标，不运行参考解生成正确答案。

语义负例包括忽略slew、错误bandwidth、忽略输出范围和memoryless响应。编译错误不计这些负例。
当前是 Spectre 扩展集候选。Python行级检查不等于实际VA校准，
Spectre、Agentic和开源复现证据分别记录。
