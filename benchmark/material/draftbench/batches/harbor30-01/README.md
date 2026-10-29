# 首批30题Harbor改造

首批30项现有资产的Harbor改造集合；保留原ID和唯一活跃题包目录，不增加独立题目计数。

用户已授权本地建设。选取、格式完成、数值校准和正式录取分别记录；本集合不是benchmark/tasks的正式清单。建设继续沿用PR255和原讨论记录。

选题清单见 [selection.json](selection.json)。题包仍由原批次维护，不复制第二套活跃目录。阶段与待定项以各题task.toml和SOURCE为准，以下不另建逐题状态。

| 序号 | 任务与材料 | 工程动作 | 同源组 |
| --- | --- | --- | --- |
| 1 | [v2-spec-024-clocked-sample-and-hold](../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) / [来源](../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/SOURCE.md) | spec-modeling | v4-024 |
| 2 | [v2-data-sampling-identification](../v2-01/tasks/v2-data-sampling-identification/instruction.md) / [来源](../v2-01/tasks/v2-data-sampling-identification/SOURCE.md) | data-modeling | jku-sampling-stage |
| 3 | [v2-integrate-349-multichannel-readout](../v2-01/tasks/v2-integrate-349-multichannel-readout/instruction.md) / [来源](../v2-01/tasks/v2-integrate-349-multichannel-readout/SOURCE.md) | extension-integration | v4-349 |
| 4 | [v2-spec-003-pipeline-adc-stage](../v2-01/tasks/v2-spec-003-pipeline-adc-stage/instruction.md) / [来源](../v2-01/tasks/v2-spec-003-pipeline-adc-stage/SOURCE.md) | spec-modeling | v4-003 |
| 5 | [v2-spec-055-first-order-sigma-delta-modulator](../v2-01/tasks/v2-spec-055-first-order-sigma-delta-modulator/instruction.md) / [来源](../v2-01/tasks/v2-spec-055-first-order-sigma-delta-modulator/SOURCE.md) | spec-modeling | v4-055 |
| 6 | [v2-spec-186-sarfend-logic-4b](../v2-01/tasks/v2-spec-186-sarfend-logic-4b/instruction.md) / [来源](../v2-01/tasks/v2-spec-186-sarfend-logic-4b/SOURCE.md) | spec-modeling | v4-186 |
| 7 | [v2-spec-002-capacitive-sar-feedback-dac](../v2-01/tasks/v2-spec-002-capacitive-sar-feedback-dac/instruction.md) / [来源](../v2-01/tasks/v2-spec-002-capacitive-sar-feedback-dac/SOURCE.md) | spec-modeling | v4-002 |
| 8 | [v3-converter-dac-linearity](../v3-01/tasks/v3-converter-dac-linearity/instruction.md) / [来源](../v3-01/tasks/v3-converter-dac-linearity/SOURCE.md) | testing-characterization | repository-owned-dac-scan |
| 9 | [v3-converter-adc-spectrum](../v3-01/tasks/v3-converter-adc-spectrum/instruction.md) / [来源](../v3-01/tasks/v3-converter-adc-spectrum/SOURCE.md) | testing-characterization | first-batch-measure-adc-spectrum |
| 10 | [v2-spec-091-chopper-stabilized-differential-amplifier](../v2-01/tasks/v2-spec-091-chopper-stabilized-differential-amplifier/instruction.md) / [来源](../v2-01/tasks/v2-spec-091-chopper-stabilized-differential-amplifier/SOURCE.md) | spec-modeling | v4-091 |
| 11 | [v2-spec-082-agc-receiver-leveling-loop](../v2-01/tasks/v2-spec-082-agc-receiver-leveling-loop/instruction.md) / [来源](../v2-01/tasks/v2-spec-082-agc-receiver-leveling-loop/SOURCE.md) | spec-modeling | v4-082 |
| 12 | [v3-ota-continuous](../v3-01/tasks/v3-ota-continuous/instruction.md) / [来源](../v3-01/tasks/v3-ota-continuous/SOURCE.md) | spec-modeling | jku-ota-dynamics |
| 13 | [v3-ota-data-model](../v3-01/tasks/v3-ota-data-model/instruction.md) / [来源](../v3-01/tasks/v3-ota-data-model/SOURCE.md) | data-modeling | jku-ota-dynamics |
| 14 | [v3-ota-step-measurement](../v3-01/tasks/v3-ota-step-measurement/instruction.md) / [来源](../v3-01/tasks/v3-ota-step-measurement/SOURCE.md) | testing-characterization | jku-ota-dynamics |
| 15 | [v2-spec-314-hysteretic-window-comparator](../v2-01/tasks/v2-spec-314-hysteretic-window-comparator/instruction.md) / [来源](../v2-01/tasks/v2-spec-314-hysteretic-window-comparator/SOURCE.md) | spec-modeling | v4-314 |
| 16 | [v2-test-offset-search](../v2-01/tasks/v2-test-offset-search/instruction.md) / [来源](../v2-01/tasks/v2-test-offset-search/SOURCE.md) | testing-characterization | v4-109 |
| 17 | [v2-spec-001-bang-bang-phase-detector](../v2-01/tasks/v2-spec-001-bang-bang-phase-detector/instruction.md) / [来源](../v2-01/tasks/v2-spec-001-bang-bang-phase-detector/SOURCE.md) | spec-modeling | v4-001 |
| 18 | [v2-integrate-case0007-adpll-fine-tdc](../v2-01/tasks/v2-integrate-case0007-adpll-fine-tdc/instruction.md) / [来源](../v2-01/tasks/v2-integrate-case0007-adpll-fine-tdc/SOURCE.md) | extension-integration | tiny-tapeout-adpll |
| 19 | [v2-repair-pfd-reset](../v2-01/tasks/v2-repair-pfd-reset/instruction.md) / [来源](../v2-01/tasks/v2-repair-pfd-reset/SOURCE.md) | diagnosis-repair | v4-family-249 |
| 20 | [v3-calibration-fractional-pll](../v3-01/tasks/v3-calibration-fractional-pll/instruction.md) / [来源](../v3-01/tasks/v3-calibration-fractional-pll/SOURCE.md) | extension-integration | fractional-pll-302 |
| 21 | [v2-test-clock-frequency](../v2-01/tasks/v2-test-clock-frequency/instruction.md) / [来源](../v2-01/tasks/v2-test-clock-frequency/SOURCE.md) | testing-characterization | v4-362 |
| 22 | [v2-spec-353-ffe-transmitter-3tap](../v2-01/tasks/v2-spec-353-ffe-transmitter-3tap/instruction.md) / [来源](../v2-01/tasks/v2-spec-353-ffe-transmitter-3tap/SOURCE.md) | spec-modeling | v4-353 |
| 23 | [v2-spec-307-switched-capacitor-integrator-phase-pair](../v2-01/tasks/v2-spec-307-switched-capacitor-integrator-phase-pair/instruction.md) / [来源](../v2-01/tasks/v2-spec-307-switched-capacitor-integrator-phase-pair/SOURCE.md) | spec-modeling | v4-307 |
| 24 | [v3-filter-ctle](../v3-01/tasks/v3-filter-ctle/instruction.md) / [来源](../v3-01/tasks/v3-filter-ctle/SOURCE.md) | spec-modeling | verilogalib-ctle |
| 25 | [v3-filter-iq-conversion](../v3-01/tasks/v3-filter-iq-conversion/instruction.md) / [来源](../v3-01/tasks/v3-filter-iq-conversion/SOURCE.md) | spec-modeling | v4-364+400 |
| 26 | [v3-filter-sweep-measurement](../v3-01/tasks/v3-filter-sweep-measurement/instruction.md) / [来源](../v3-01/tasks/v3-filter-sweep-measurement/SOURCE.md) | testing-characterization | original-filter-measurement |
| 27 | [v3-filter-programmable-lp](../v3-01/tasks/v3-filter-programmable-lp/instruction.md) / [来源](../v3-01/tasks/v3-filter-programmable-lp/SOURCE.md) | extension-integration | v4-334 |
| 28 | [v2-repair-uvlo-reset-chain](../v2-01/tasks/v2-repair-uvlo-reset-chain/instruction.md) / [来源](../v2-01/tasks/v2-repair-uvlo-reset-chain/SOURCE.md) | diagnosis-repair | original-uvlo-chain-case0009 |
| 29 | [v2-test-comparator-delay](../v2-01/tasks/v2-test-comparator-delay/instruction.md) / [来源](../v2-01/tasks/v2-test-comparator-delay/SOURCE.md) | testing-characterization | v4-170 |
| 30 | [v2-test-gain-settling](../v2-01/tasks/v2-test-gain-settling/instruction.md) / [来源](../v2-01/tasks/v2-test-gain-settling/SOURCE.md) | testing-characterization | case-0018+v4-038+v4-370 |

本轮30题已完成本地Harbor实现稿，包括原位`/app`交付、英文合同、公开起始工程与自测入口、参考安装脚本和独立评分镜像。分类为14道规格题、2道数据题、4道集成题、2道修复题、8道测试题。全部保持`implementation`，`review_status=pending`，`grading`和`runtime`待完成；正式录取仍为0。

30题包装检查、官方Harbor配置解析、6类Docker交付恢复检查和9组合成进程边界检查通过。评分镜像初始`/app`为空，缺交付物不会回退到starter。上述检查没有执行电路；本机未发现Spectre，完整Harbor端到端执行和当前版本科学校准尚未验证。历史作者证据保留原身份。

C109、U17、DLL、DCC和CPPLL的既有科学未决不在此批暗中解决。C056已有200ps默认孔径及不重叠边界，本批优先改造现成024，不将其后置解释为孔径数值未知。

Grok初选中的持续失调校准和LDO响应实验，因SOURCE属于必须保持原路径的冻结材料，本批改选可编程低通扩展与增益/有限建立测量；原两题保留后续迁移候补，工程价值判断不变。

两组新上下文Astra独审覆盖30题合同与共同入口。A组发现的5处辅助路径遗漏已修正，并经包装增量独审确认闭合。B组的公式措辞、公开元数据、跨线职责和多文件说明由主控按原依据修正；PLL相位统计量的两种口径明确列为待定。包装增量独审无新增发现。原报告及修正核对见本轮交付收据（`runs/t3-harbor30-20261027/final-delivery.json`）。

r2交付时，024观察窗口、055逻辑低电压、307饱和状态和PLL相位统计量是待解决的科学缺口；它们的现状见下一段。各题`SOURCE.md`其余缺口仍需解决，再完成匹配版本的后端运行与作者校准。本地30题归档（`runs/t3-harbor30-20261027/harbor30-implementation-r2.tar.gz`）供检查和交接，未发布；归档中的来源文档链接仍按原仓库解析。

2026-10-27接续已把这四项补成原`SOURCE.md`中的“评分合同决定卡”。024持续保持及055过渡后观察的漏检有合成反例，可依据已有合同修复；本轮未改checker。仍需选择的是055低电压编码、307是否夹位递推状态，以及PLL相位统计量连同展开约定。建议、区分反例与影响已逐题列明，尚未采用。补充材料不包含在原r2归档，不扩用旧审核资格；本轮材料与检查（`runs/t3-harbor30-20261027/grading-decisions/decision-material.json`）保留独立身份。

同日用户确认了这三项：055的`bit=0`及首个时钟沿前为0V，沿用±2mV；307夹位递推状态，饱和后的反向样本当拍退出；PLL对连续展开的相位序列取`abs(mean(phi))`不超过0.2周期，同一序列峰峰值不超过0.35周期。三题题面、`SOURCE.md`和[selection.json](selection.json)已同步。参考解和这三处公式原本就按所选语义计算，没有改数值代码；024与055的公私checker按已有合同修复了完成时刻和`tr`后观察。合成判据控制与红绿检查见采纳记录（`runs/t3-harbor30-20261027/grading-adoption`），没有执行电路。这批增量的独立审核记录在本线决策日志；后端运行与作者校准仍待完成。

EVAS跨线需求也保留在同一份 [selection.json](selection.json) 的各题 `evas_requirements` 中，逐题给出行为组合、当前参考写法的身份、声明后端依据与未决条件。它供EVAS主控只读规划，既不声明EVAS已经支持，也不限定求解者必须采用参考解的算子。两道数据题使用既有晶体管数据，不能用EVAS输出替换真值。C109/Q2等候补科学条件仍未决定。

同日用户决定首批优先不需要SPICE网表的纯Verilog-A题。原第29题[v2-test-por-sequence](../v2-01/tasks/v2-test-por-sequence/instruction.md)含sky130 MOS子电路、R/C/I器件和SPICE语言网表，移出首批，题包保持现状，作为Spectre/SPICE路线后备；它的原记录连同`evas_requirements`完整保留在selection.json的`spice_route_reserve`中。第29题改由同批草稿v2-test-comparator-delay补位，已迁成与其余29题相同的本地Harbor形式，题面合同数值与迁移前一致，动作分布仍为14/2/4/2/8。迁移的包装、配置解析和独立评分镜像检查见替换记录（`runs/t3-harbor30-20261027/por-swap`），没有执行电路。新上下文Astra独审发现两处措辞问题：SOURCE和selection把原题已定的0.45 V检测门限列成待定；公开指南称有独立`.scs`文件，而本题没有。两处已由主控修正并逐文件哈希核验；首批另有10份没有`.scs`文件的指南带同一句，已一并改正。后端运行与作者校准仍待完成。

全部候选的仿真路线分类（`benchmark/material/draftbench/planning/simulation-routes/README.md`）显示，现行首批30题都是纯Verilog-A题。其中14题含EVAS文档或源码写明的缺口，已按影响排序提为[#270](https://github.com/BucketSran/vaEVAS/issues/270)，台架不改。11题的缺口位于台架或固定支持模型，涉及正弦源、输出点上限、`transition`动态延迟、`$rtoi`、`idt`电压复位、层次节点保存、普通`floor`和运行期移位量；另3题只涉及参考解或有条件的写法。静态清单不能保证完整，已请EVAS线用自己的前端核对。各题缺口另记在selection.json的`evas_requirements.evas_documented_gaps`。

2026-10-28评分起点（F01）：v2_spec.py在目标变化后`1.15*tr`（091为`4.1*tr`）内不评分，4道测量题在每个事件前后各80 ps内不评分，题面原先只写了到达期限或guard。用户确认（经总协调，“全部按推荐”）题面写明checker实际的观察起点，checker不动，每题加迟到负例，测量题另加提前负例。受影响的13题（001、002、003、082、091、186、307、314、353与clock-frequency、comparator-delay、gain-settling、offset-search）已改题面并加`tests/calibration`三件，checker、用例与参考解逐字节未改；合成控制161项与预期一致，旧版EVAS 0.8.7上84/86例符合被拒矩阵（不符2例为091层次保存列在旧版返回全0），186与gain-settling的候选旧版跑不了，矩阵条目待定。改动见修改记录（`runs/t3-harbor30-20261027/f01-r1/disposition.md`）；增量独审对F01改动无可操作发现。另查出314清零取消脉冲、001的`td`两处题面与checker不一致，独审核实为P2，现有用例不触发，建议改checker、保留题面与参考解，排入下一轮修正。这两处已按建议修正：first30-fix-r1、r2改了两题的checker，first30-fix-r3给001补了私有用例`contract-held-clear-clk`；三轮的增量复审都已关闭，最后一轮只有一条记录措辞（F30R3-01），主控已改（r3记录（`runs/t3-harbor30-20261027/first30-fix-r3/disposition.md`））。新用例与新候选按新身份在D2做Spectre校准。

2026-10-29 触碰门限（决定单第 4 项，A 收窄版；v2spec-touch-r1，未仿真）：首批 11 道 v2-spec 题（001、002、003、024、055、082、091、186、307、314、353）题面补写“外部驱动的逻辑输入到达门限必定穿过、不触碰后返回、不停在门限上”一句，点名本题的信号与门限（001 新增；314 与另 9 题由原句“不停在门限上”合并），SOURCE 各加一节核对记录。题包全部网表按有理数精确核对，停在门限、触碰后返回、t = 0 恰在门限都是 0；186 系统台架的比较器对由固定模块驱动，另以已核收 D2 波形核对。checker、用例、网表、参考解未改，不需要新的 Spectre 作业。见记录（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
