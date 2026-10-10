# 既有 ADC 频谱合成观测资产

现有目录：[measure-adc-spectrum](../../tasks/measure-adc-spectrum/SOURCE.md)。来源组保持 `first-batch-measure-adc-spectrum`，工作区资产 ID 为 `first-batch-adc-spectrum`。本轮读取身份见 [来源卡](../sources/vaevas-behavioral-seeds.md)。

原 `device.va` 生成带二三次谐波的信号并量化到 12-bit unsigned 码，通过 code 电压与 clk 提供观测。参考 VA 模块在 64 次有效边沿采集码值并计算指标。它已有明确电路性能解释，但仍是行为合成数据，没有实际器件或测量来源。

新 case 用这套资产研究如何让已有 ADC 记录进入 VA 测量流程。输入回放、记录边界、可用参数和异常状态尚待重定，不能直接沿用旧题的工具链限制或宣称旧 checker 已覆盖新合同。[ADCToolbox](../sources/adctoolbox-spectrum.md)提供指标交叉检查方法，不与候选代码共享唯一真值算法。

本轮不改变原任务，不新增其重复计分项。若后续换真实 ADC 数据，应保存采集条件和出处，并按是否改变工程合同决定替换环境还是另建关联 Case。
