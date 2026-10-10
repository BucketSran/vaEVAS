# 旧 Testbench 如何改成 VA 测试任务

2026-10-10。本轮实读 v4-749 PFD 与 v4-875 非重叠时钟的公开题面、机器合同、评分策略和 checker profile，并读派生 runner 的运行与结果判定代码。来源身份与全量规模见[迁移入口](README.md)。没有运行两个测试台，也没有逐个审计它们的语义负例。

本页保留早期两包筛选范围。GLM 全量审核启动后的进度、更多候选与按最新测量价值标准的复核，见[阶段移植建议](https://github.com/BucketSran/vaEVAS/blob/83ddca7b9ede6d4211b172827f26064eca5577b3/benchmark/workbench/migration/v4-testbench-glm-triage.md)。后续建议包括复用旧 DUT 形态中的现成 VA 仪表，不受旧 Testbench 标签限制。

## 旧题实际要求什么

[v4-749 题面](../../reference/v4/release/benchmarkv4-r53/tasks/749-pfd-active-low-reset-testbench/public/instruction.md)和 [v4-875 题面](../../reference/v4/release/benchmarkv4-r53/tasks/875-nonoverlap-clock-generator-testbench/public/instruction.md)都要求交付一个 `testbench.scs`。求解者设计激励、连接只读 DUT 并保存公开波形；不交付 VA 观测模块或自行报告通过/失败。固定 oracle 用同一份 deck 检查健康 DUT，再判断是否能暴露五个匿名行为负例。

[runner](../../reference/v4/runners/derived_testbench_oracle.py)把 `invalid_run` 与 `killed_behaviorally` 分开。这个思路值得保留：运行失败不能算检出了电路故障。但执行依赖外部 `simulate_evas` 及具体 checker；本轮读取的 profile 只有私有 checker 身份和信号合同，不足以证明迁入目录可直接恢复整个评分流程。

因此，旧 Testbench 适合提供**刺激哪些行为、如何用健康与故障 DUT 校准测试**的素材。若新题要考 VA 测试模块，交付物和验收责任需要重新设计；不能把 `.scs` 原题直接登记为已完成的 VA 测试题。旧五负例配额也无需继承。

## 两种可保留的改编方式

| 形式 | 给求解者什么、提交什么 | 出题者独立检查什么 |
| --- | --- | --- |
| 固定公开激励，写 VA 观测/检查模块 | 固定可读 DUT、连接、行为要求和激励；提交测量值或违规事件的 VA 模块 | 从 DUT 实际波形独立推导指标/违规，核对漏报、误报与时间定位；不能只读候选的通过标志 |
| 固定工程连接，写 VA 激励及测试模块 | 固定可读 DUT、接口和实验目标，允许自定义输入序列与公开观测 | 独立核对激励确实覆盖要求、健康 DUT 能通过、故障能暴露；是否要求候选自行判定需在题面说明 |

两者都属于电路测试与表征。可以做只生成激励的限定环节题，也可做激励到测量、判定的完整流程题；不必给每个 DUT 各出一套。Agent 解题时自建的临时测试台是解题工具，不因此额外成为一道评分任务。

## 两个具体来源怎么用

**PFD（family 249）**：已有 case-0008 使用同族修复素材。测试方向可让 VA 激励产生“ref先到、fb先到、单边状态时外部复位、双方到达后的互复位”等场景；VA monitor 若纳入交付，检查 UP/DOWN 的建立与清除。先澄清同刻事件、挂起复位和参数范围，再选定负例。未来建卡应继续用 `v4-family-249`，本轮不为凑三形态重复建卡。

**非重叠时钟（family 375）**：可以测 phi1/phi2 的互斥、死区、reset/enable 和短请求行为。但[规格筛选](v4-spec-screening.md)已发现 reference 没用 tr 平滑，死区又受全局 timer 相位影响。应先确定健康 DUT 的外部合同，再开发测试题；不能拿有疑点的实现定义“正确”。

另有旧首批 [verify-nonoverlap-stimulus](../../tasks/verify-nonoverlap-stimulus/instruction.md)，原交付物已经是 VA 两相激励，题面还通过下游采样路径考察实用效果，比 `.scs` 交付更接近当前方向。其 `first-batch-verify-nonoverlap-stimulus` 来源组与 v4-family-375 不同，不能因题材相似就认定共源。本轮仅阅读题面和 SOURCE，未重审其 checker 或复用旧运行资格。

旧首批 [verify-sar-flow](../../tasks/verify-sar-flow/instruction.md)也可提供 VA 激励与自动判定的流程例子，但被测 ADC 是抽象码转换/握手模型；它不能证明已有由采样、比较器、DAC 和 SAR 逻辑组成的完整系统建模题。

本轮结论是保留迁移路径、暂不增加 Testbench 派生卡。现有 POR、LDO、运放和 ADC 频谱四个测试方向继续推进；后续若需要基础 VA 激励题，再比较旧首批非重叠时钟与 v4 改编的投入和工程意义。
