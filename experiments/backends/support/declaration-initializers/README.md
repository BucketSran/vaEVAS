# 事件状态的有限声明初值

本切片复用现有初态绑定，为原本已有cross/timer写者的标量绑定有限实例常量。
声明种子全部验证后，再按原顺序执行initial_step；完整类型、角色和拒绝边界见
[数学合同](../../../../evas/docs/math/events.md#declaration-initializers)。未增加IR或运行期机制。

[候选与验收收据](evidence.json)记录13项新回归、独立审查和五原件结果。
110/115完整通过原checker；017保持角色拒绝，039保留另一个原文件的语法阻塞，112保留随机函数语法拒绝。
最终统一400的源码与结果在[完整收据](../integer-bitops/evidence.json)绑定，原件子集不能重复计分。

语法参考固定MIT旧版EVAS；OpenVAF只核对声明元数据与变量初始化入口，未复制GPL源码，
也未用其尚未完成的通用事件控制作为事件顺序答案。具体版本、标准章节和检查身份见收据。
原VA、波形、二进制及源码冻结包保留为local-only；仓库只保存公开缩减回归与紧凑元数据。

一般输入电压采样仍只有[设计与正反例](../initial-voltage-sampling/proposal.md)，未实施。
当前推进见[Issue214](https://github.com/BucketSran/vaEVAS/issues/214)，PR208继续草稿，未合并。
