# ADCToolbox：ADC 频谱指标的计算合同

固定版本：[Arcadia-1/ADCToolbox，8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9](https://github.com/Arcadia-1/ADCToolbox/tree/8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9)。

2026-10-10 重读 [compute_spectrum.py](https://github.com/Arcadia-1/ADCToolbox/blob/8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9/python/src/adctoolbox/spectrum/compute_spectrum.py)、[SNDR 单测](https://github.com/Arcadia-1/ADCToolbox/blob/8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9/python/tests/unit/spectrum/test_compute_spectrum_sndr.py)和 [LICENSE](https://github.com/Arcadia-1/ADCToolbox/blob/8d62fb1863e38ffe5c6cc3ac48fa9c24d9df1ae9/LICENSE)。本轮未运行这些测试，也未完整审计所调用的所有辅助函数。

主函数接收离散 ADC 数据，包含窗函数、基波邻域、带内范围和功率处理；SNDR 从基波与剩余带内功率计算，SFDR 使用最大杂散，ENOB 由 SNDR 换算。单测使用固定随机种子的正弦加噪声，也涉及量化 SAR 数据。MIT 版权署名 Zhishuai Zhang、Lu Jie，复用保留声明，研究使用遵循其引用说明。

## 对题目设计的用途

本库为指标定义和交叉校准提供方法，不是可直接交给 Agent 的 VA 测量器。新题须公开采样、码值解释、DC、Nyquist、窗、谐波和异常记录约定；不能把该函数的默认设置视为题目隐藏标准。

工作区先复查 [仓库已有频谱资产](../circuits/first-batch-adc-spectrum.md)。固定回放器将观测转换为 code/clk 电压端口，Agent 负责 VA 采样与指标计算。参考数值由独立实现及已知信号验证，不仅比较两个调用同库的结果。已有合成模型不标成真实 ADC 实测数据；实测或晶体管记录的来源仍待另行选定。
