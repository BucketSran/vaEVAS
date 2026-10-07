# PLL锁定与跳频来源与边界

这是根据工程需求原创的动态辨识题。数据身份是 `behavioral_synthetic`，
不声称器件电路仿真、silicon测量或厂商模型输出。
一手工程参考为 [PLL锁定与跳频](https://www.analog.com/en/resources/analog-dialogue/articles/pll-synthesizers.html)，只支持架构与指标的工程意义。
一手资料说明频率跳变、容差和loop bandwidth决定lock time。本题是原创phase-feedback抽象闭环，不宣称复刻厂商器件或包含RF/charge-pump物理。

作者生成器与独立目标在 `experiments/benchmark_first_batch/identification/`。
公开与隐藏部分按完整实验划分，同一个固定系统只改变题面允许的刺激。
参考解只从公开观测估计可行参数，不使用终评系数。
checker逐条检查局部样点、时序或性能指标，不运行参考解生成正确答案。

语义负例包括错误阻尼、取消积分路径、错误loop时间尺度、伪造已锁相时钟和粗网格混叠纹波。编译错误不计这些负例。
当前是 Spectre 扩展集候选。Python行级检查不等于实际VA校准，
Spectre、Agentic和开源复现证据分别记录。
