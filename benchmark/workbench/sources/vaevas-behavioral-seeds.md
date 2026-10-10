# vaEVAS 既有行为任务：UVLO 与 ADC 频谱

固定核查版本：[c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9](https://github.com/BucketSran/vaEVAS/tree/c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9)。2026-10-10 读取下列源文件。两项是仓库原创行为资产，属于不同电路来源组，不能因同处本仓库合并为一个来源组。

| 资产 | 本轮实际读取 | 现有内容 |
| --- | --- | --- |
| UVLO 计时取消故障 | [SOURCE](../../tasks/repair-uvlo-recovery/SOURCE.md)、[题面](../../tasks/repair-uvlo-recovery/instruction.md)、[starter](../../tasks/repair-uvlo-recovery/environment/public/starter.va)、[uvlo_targets](../../checkers/first_batch_model_repair.py) | 资格时间、迟滞、复位重启合同；人工删去取消/发布再检查；独立 token 事件队列 |
| ADC 频谱测量 | [SOURCE](../../tasks/measure-adc-spectrum/SOURCE.md)、[题面](../../tasks/measure-adc-spectrum/instruction.md)、[device.va](../../tasks/measure-adc-spectrum/environment/public/device.va)、[VA 参考测量器](../../tasks/measure-adc-spectrum/solution/dut.va) | 合成量化码和二三次谐波、有效时钟、64 点相干 DFT 的 SNDR/SFDR/DC |

UVLO 的工程动机是短暂越过门限不能解除复位；已有实现为单模块，新增系统卡需要另建 reset-release 与 enable-gate 等真实协作。ADC 的 code 电压数值表示 unsigned 码，已有题规定谐波计入噪声失真、DC 排除、Nyquist 单独归一化。它可作为已有观测回放的基线，不把合成器参数标成器件实测真值。

两项源文件都属于旧首批资产。此次静态读取不重新认证其历史运行，也不把已有题再算作新增评分题。新卡只记录筛选和改编方向，运行、checker 与后端资格需要绑定新合同复查。沿用本仓库资产约定；后续若混入外部数据或器件库，单独登记来源和许可。

旧题含语言子集和“编译/超时即零分”等历史约束，**不作为新题默认政策**。新题服从 [当前 benchmark 合同](../../README.md#评测方式与题目建设)，区分候选错误与环境能力缺陷。

## CDR 判相模型与 v4 的派生关系

2026-10-10 继续阅读 [spec-cdr-phase-detector 题面](../../tasks/spec-cdr-phase-detector/instruction.md)和[SOURCE](../../tasks/spec-cdr-phase-detector/SOURCE.md)。来源说明明确需求参考 v4-001，VA、网表与 checker 独立编写。因此保留旧 cdr-phase-original 标签，并在 case-0012 关联 v4-family-001，避免把需求派生素材当作独立电路来源。本轮未重新审计该派生任务的 reference、checker 或运行资格；题面的同刻事件排除与数值容差不能替代 retiming 的工程依据。
