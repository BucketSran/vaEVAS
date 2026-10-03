# 数学原理章节

按主题阅读；主线：贡献汇总成方程 → 联立求解 → 历史与事件推进 → 组合闭环。

| 章节 | 内容 |
| --- | --- |
| [solving.md](solving.md) | 电压方程、稠密/稀疏线性代数、Newton、工作点验收与精度链 |
| [events.md](events.md) | 事件定位、条件、顺序赋值与同刻联立关系 |
| [operators.md](operators.md) | 直接输入算子（transition/absdelay/slew/idt/相位）的公式、历史和误差 |
| [continuous.md](continuous.md) | 联合状态方程、DAE、误差传播、复位闭包与动态 guard |

同一算子可经不同路径求解（如直接 PWL 的 `idt` 用解析积分，带反馈的 `idt`
进入联合连续网络）；不能把单一路径的限制读成整个算子的限制。
