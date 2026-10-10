# Alexander BBPD 的结构与模型边界主源

本来源卡服务 case-0012 r2。2026-10-10 核对以下两份作者提供的原文，仅引用结构、判相原理和建模边界，不复制图表、全文或代码到任务包。

| 主源身份 | 实读范围 | 用于本题的内容与限制 |
| --- | --- | --- |
| Behzad Razavi，Challenges in the Design of High-Speed Clock and Data Recovery Circuits，IEEE Communications Magazine，2002-08，pp.94–101；[作者PDF](https://www.seas.ucla.edu/brweb/papers/Journals/BRAug02.pdf) | 印刷p.96 Fig.3图像、p.97 Alexander段落 | 三点采样、寄存器历史对齐与XOR关系；原文早晚标签有内部不一致，详见学习说明，按已声明的时序重新推导 |
| Ken Kundert，Verification of Bit-Error Rate in Bang-Bang Clock and Data Recovery Circuits，Version 1c，2010-05-04；页首说明更新至2022-06-11；[作者PDF](https://designers-guide.org/analysis/bang-bang.pdf) | §4方向与调速，§5模型层次，§6.2亚稳态与抖动的讨论 | 区分判相方向、后级调速和实际小相位差效应；不把相位域平均模型当作本题逐边沿实现 |

可核对的采样推导、图文不一致及旧源码差异集中在 [Alexander 学习说明](../migration/alexander-bbpd.md)。本轮不是两篇论文的完整复现或全文精读，没有核验可分发的配套电路工程。

r2 的接口、启动规则、输出保持、010/101门控、窄重合窗口和独立 checker 均为本项目提出的公开合同。特别是10 ps窗口及输出容差不是论文给出的器件参数，仍须 review 和数值校准。此来源不增加新的真实电路资产，也不消除与旧 v4-001 需求的派生关联。
