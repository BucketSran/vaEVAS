# 时钟可调SC滤波器来源与边界

这是根据工程需求原创的动态辨识题。数据身份是 `behavioral_synthetic`，
不声称器件电路仿真、silicon测量或厂商模型输出。
一手工程参考为 [时钟可调SC滤波器](https://www.analog.com/en/products/max7400.html)，只支持架构与指标的工程意义。
厂商文档支持时钟控制corner frequency的工程意义；本题原创两节低通而不是其八阶椭圆架构。

作者生成器与独立目标在 `experiments/benchmark_first_batch/identification/`。
公开与隐藏部分按完整实验划分，同一个固定系统只改变题面允许的刺激。
参考解只从公开观测估计可行参数，不使用终评系数。
checker逐条检查局部样点、时序或性能指标，不运行参考解生成正确答案。

语义负例包括丢失一节动态、使用下降沿、丢失历史、错误增益和每个低时钟相位清零。编译错误不计这些负例。
当前是 Spectre 扩展集候选。Python行级检查不等于实际VA校准，
Spectre、Agentic和开源复现证据分别记录。

<!-- generated first-batch metadata -->
- `engineering_action`: `from-data-modeling`
- `source_group`: `original-identified_sc-identification`
- `context_level`: `bounded-work-unit`
- `provenance`: `original-engineering-requirement`
- `data_provenance`: `behavioral_synthetic`
<!-- end generated first-batch metadata -->
