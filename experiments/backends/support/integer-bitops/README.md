# 有限整数位运算与点值证明

[紧凑收据](evidence.json)记录有限整数位运算、transition点值证明、算子默认参数和有限声明初值的分支验收。
当前通过数与剩余缺口在[统一进度表](../../../../evas/docs/COMPARISON.md#progress-board)维护，
排期与逐项推进见[Issue214](https://github.com/BucketSran/vaEVAS/issues/214)。PR208保持草稿，未合并。

位运算复用IR24的比较选择，不增加Rust指令。源类型、signed32位模式、有限域、
中间溢出和完整操作数读取义务见[数学合同](../../../../evas/docs/math/events.md#integer-bitops)。
纯整数事件右侧只枚举一次有界状态网格，继续使用原256域、4096决策与100000项IR上限。
公开回归有独立定宽答案、顺序PRBS、普通掩码、同刻读取和拒绝控制。

transition复用已有有理起点、折线与终点证明，同时计算名义点值和向外包围。
这修复了已知物理时间被代表上界替代的位移。真实非点目标、窗口、采样历史、
舍入与下游放大仍按原预算验收。范围见[算子合同](../../../../evas/docs/math/operators.md)。
公开PWL反例在原1e-12预算下先拒绝，再与独立Fraction答案一致；过严的1/3预算仍拒绝。

最终收据绑定同一144文件源码、release核、原checker和normalization，完整执行400原件：
198通过、18失败、184拒绝，清理400/400。此前核心400与后续三件的独立身份保留在1de6896b历史收据。
[有限声明初值](../declaration-initializers/README.md)随最终候选复验；当前成绩来自完整重跑，未从局部结果相加。
012保留原checker覆盖不足，023/027、048/049、097/349保留各自后续阻塞。
初始化仅交付[设计与正反例](../initial-voltage-sampling/proposal.md)，没有实现采样扩展。

调研依据VAMS LRM2.4的类型和位逻辑规则；旧EVAS固定`6cb6fa7a7dac70fc0d4120126d8cf74258e6637b`
用于核对parser优先级。OpenVAF-Reloaded固定`5063fdadc254842cdf16112241d6df81fde48d43`
提供parser与整数MIR对照，未复制其GPL代码或signed右移语义。
默认参数按LRM2.4 §4.5.5、§4.5.9复用既有idtmod与slew。

完整输入、原件、源码冻结包、二进制、波形和过程日志为local-only，路径和哈希在收据中。
早期失败与取消运行保留，未计为通过。仓库提供公开缩减回归和紧凑来源，
不宣称原始材料全部可公开下载。未增加实际Spectre对齐、全时域或共同Q资格。
