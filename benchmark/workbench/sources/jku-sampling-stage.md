# JKU：SKY130 transmission-gate 采样级

固定来源：[efabless/SKY130_SAR-ADC1](https://github.com/efabless/SKY130_SAR-ADC1/tree/892272208df28b6c7620101e129a9d8dd95ebab7)。
版本：`892272208df28b6c7620101e129a9d8dd95ebab7`。
作者：Manuel Moser，JKU Linz / Institute for Integrated Circuits。README 记载 2023 年硕士论文项目，所读原理图版权为 2022 年。
许可：[Apache-2.0](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/LICENSE)。

## 实读范围

2026-10-10 按固定 commit 重新读取 README、LICENSE、以下器件/台架文件和设计笔记，并检查 GitHub recursive tree。树返回 `truncated=false`，未列出 `.va`、`.vams` 或 NOTICE 文件。该检查只覆盖此仓库版本，不能证明其他来源没有 VA 模型。

- [adc_gate_tb_transient.sch](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_gate_tb_transient.sch)：完整瞬态台架与数值配置。
- [adc_gate_switch.sch](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_gate_switch.sch) 和 [adc_gate_switch.sym](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_gate_switch.sym)：主传输门、输出 dummy 与端口对应关系。
- [adc_inverter.sch](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_inverter.sch)、[adc_inverter.sym](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_inverter.sym) 和 [adc_inverter.spice](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/xschem/adc_inverter.spice)：实际 CMOS 互补控制生成电路及已有 SPICE 子电路。
- [doc/adc_gate_switch.md](https://github.com/efabless/SKY130_SAR-ADC1/blob/892272208df28b6c7620101e129a9d8dd95ebab7/doc/adc_gate_switch.md)：采集/保持设计目标、选型与作者的 corner 分析文字。没有读取所链接图片的像素或复算图中曲线。

本次没有运行原电路、候选 VA、辨识训练、checker 或仿真器，也未取得采样台架独立原始波形。已有研究报告和仓库顶层 ADC 性能说明不作为本次采样级复现证据。

## 可用资产与原参数

真实器件来源是 SKY130 `pfet_01v8` / `nfet_01v8` 传输门。主 PMOS/NMOS 均为 `W=7.6, L=0.22, nf=4, mult=1`；输出端 dummy 均为 `W=3.8, L=0.22, nf=2, mult=1`，源漏接输出 `b`，控制与主器件互补。设计笔记明确将其用于 charge-injection compensation。原理图还包含结面积/周长等几何表达式，重建网表时应保留。

台架将 `in` 接开关 `a`，`out` 接 `b` 和对地保持电容 `C1=2.44p, m=1`。`nsample` 直接驱动开关 `sw_n` 和 inverter 输入，inverter 输出 `sample` 驱动 `sw`。inverter PMOS 为 `W=0.84, L=0.15, nf=2`，NMOS 为 `W=0.42, L=0.15, nf=1`。从拓扑推断，外部 `nsample` 低时跟踪、高时保持；实际沿延迟和电平转换仍须仿真确认。

| 台架项 | 固定源文件中的设置 |
| --- | --- |
| 外部控制 V3 / `nsample` | `0.9 pulse(1.8 0 5n 1p 1p 10n 20n)`，延迟 5 ns、低电平脉宽 10 ns、周期 20 ns |
| 输入 V6 / `in` | `0.9 pulse(1.8 0 20n 1p 1p 20n 40n)`，延迟 20 ns、低电平脉宽 20 ns、周期 40 ns |
| 供电 / corner / 温度 | `V4=1.8`、`corner=tt`、`.temp = 25` |
| 保存与运行 | `.save all`、`.OPTIONS savecurrents`、`.tran 10p 65n`；control 中 `run` 和 `plot v(sample) v(in) v(out)` |
| 数值配置 | `RELTOL=.1 TRTOL=1 ABSTOL=1e-20 CHGTOL=1.0e-20 DEFAD=1.0e-18`；`method=gear` 行被注释 |

两个源的前置 `0.9` 值与 pulse 的初始值 `1.8` 同时存在。原台架没有显式 `.ic`、`.nodeset`、`uic`、reset 或输出电容初压合同；不能把 `0.9` 擅自解释为已证明的保持电压初态。数据生成前需固定网表化结果、工作点与 transient 初始化语义，并保存可见前置历史。`.tran 10p` 也不证明内部最大步长或最终导出网格已经固定。

## 动态证据与待表征项

设计笔记把 20 ns 内采集至 12-bit 的 1 LSB 精度作为用途，并推导 `Ron < 985 ohm`、`tau < 2.4 ns`。作者写明选型在 `tt / 25°C` 满足目标，在 `ff / 100°C` 不够；这是源文档叙述，本次没有复验。该 20 ns 设计目标与瞬态台架的 10 ns 低脉宽不同，不能直接把目标抄成当前台架的实测结果。

同一笔记讨论保持误差、charge injection 与 leakage，给出约 13.14 pA 的 leakage 上限。它在保持时长推导中分别使用 82.2 μs 和 81.6 μs，当前 65 ns 台架没有覆盖该长保持窗口；这一差异需要在正式数据合同前厘清。

结构支持研究有限采集、输入相关建立、前拍状态延续及沿附近 pedestal/clock feedthrough。其幅度、数值稳定性和可辨识性尚未知，dummy 的存在也不能证明注入完全消除。保持 droop 未证明高于数值不确定性，不预先列为必评分指标。公开表征应分别改变跟踪时长、输入电平/方向、前拍状态和输入/clock 相位，并在完整连续记录上确认目标动态。

## 许可、模型与使用边界

所读原理图带 Manuel Moser 的 Apache-2.0 notice，根 LICENSE 与 README 的许可说明一致。复用源码需保留许可与归属，改编文件注明修改。SKY130 模型、corner 符号和 xschem 通用器件库是外部依赖，实际版本、文件许可和发布范围尚未固定，不能由本仓库 Apache-2.0 推断全部依赖都已完成许可复核。

此固定版本没有发现现成采样级 VA 模型。可复用的是晶体管原理图、符号、inverter SPICE 和表征起点，不是已校准的行为替代模型。源采样台架也没有独立 SPICE deck/数据包的已复现证据；PDK 依赖、网表生成、后端版本与容差/边沿/步长对照均待完成。

候选方向保持为真实采样级固定数据包动态辨识，交付电压域 VA，固定供电、温度、corner 和 hold C。第一阶段不向解题 Agent 开放查询原电路；Agent 仍可按题目提供的后端仿真自己的候选并使用公开自测。主动补表征属于后续独立阶段。旧行为模型合成题或参考 VA 输出不能冒称该晶体管电路表征数据。

后端选择与验收按当前 benchmark 合同办理，不从原台架的 ngspice 入口推导正式评分已可用，也不把历史研究报告中的 Spectre 建议当成已完成校准。尚需真实源数据包、可辨识性检查、独立判据及正例/负例校准；本来源卡不表示正式题目已建成。
