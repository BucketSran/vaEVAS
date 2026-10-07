# 首批元数据映射

工程动作对应 benchmark README 已确定的七类工作目标。`engineering_action` 描述任务要求，Harbor 的 `category` 保持原值，不用于统计七类覆盖。

| 中文合同 | engineering_action |
| --- | --- |
| 按规格构建模型 | specification-modeling |
| 从数据建立模型 | from-data-modeling |
| 扩展与集成 | extension-integration |
| 诊断与修复 | diagnosis-repair |
| 开发验证工具 | verification-tools |
| 测量与表征 | measurement-characterization |
| 改善仿真实现 | simulation-implementation-optimization |

`context_level` 使用 `bounded-work-unit`、`bounded-small-project`、`complete-repository`，分别对应单个工作单元、有边界的小工程、完整仓库任务。当前 35 个正式资产中，30 个为 bounded-work-unit、4 个为 bounded-small-project、1 个为 complete-repository。TDC 为 complete-repository，其余四个 integration 为 bounded-small-project，其他条目为 bounded-work-unit。TDC 是原创教学和研究仓库，不声称工业版本史。

`provenance` 描述任务问题的来源，不描述某段参考代码是否原创。

| provenance | 适用范围 |
| --- | --- |
| original-engineering-requirement | 根据明确工程需求原创的建模、辨识、集成、验证、测量与优化问题，含复用的 va08 |
| injected-semantic-fault | 本批原创工程上人工注错的四个 repair 任务 |
| development-regression | 来自实际开发失败的 va07 振荡器修复题 |

`data_provenance` 单独记录数据或器件观测来源。原创电压域行为系统使用 behavioral_synthetic，不代表实测或晶体管表征。va07 不提供辨识/表征数据，使用 not-applicable；其实际后端执行结果仍属于独立校准证据。任务来源字段不替代源码许可、执行收据或 SOURCE 中的历史来源说明。

35 个正式资产共有 32 个 source_group。共享电路资产必须保留共同 source_group。ΣΔ spec/repair、UVLO spec/repair 已关联；周期 S/H 验证与测量使用 original-periodic-sh-observation，二者分别交付故障判定器和指标测量器，保持独立 task id。其他电路同名不自动合组。

复用题采用具体资产身份：va07 使用 repository-triangle-oscillator，va08 使用 repository-owned-original-adc-linearity。旧 TOML 值 repository-owned-regression、repository-owned-original 是过往宽泛来源分类；不得用它们把同一任务再次计入不同来源组。旧冻结包保留原字节和原身份，当前登记更新不改变历史结果。

各建设生成器可以保留现有结构。每次生成后运行：

```sh
python3 -B experiments/benchmark_first_batch/sync_metadata.py
python3 -B experiments/benchmark_first_batch/sync_metadata.py --check
```

normalizer 仅修改五个首批登记 JSON、所属任务 task.toml 和 SOURCE.md。它不修改 instruction、cases、checker、solution 或公开数据，并检查这些任务文件的内容身份保持一致。SOURCE 保留人工说明，补充统一的机器可读 metadata 块。

优化登记分别保留 `tasks` 与 `candidates`。当前 `tasks` 中是 VCO、电源监控、SAR、UART 和 Flash 五个已准入的正式资产；`candidates` 中是采样 DAC 和 SC 系数计算两个候选。normalizer 保持 `candidate_count`、`task_count`、资格与结果状态的原值；字段统一不授予准入资格，也不证明完整正式评分校准已完成。

映射遵循用户已确定的七类工程动作、三种上下文、人工故障/真实开发问题/原创需求的区别、同源关联及合成数据如实标记。题量、后端校准、Agentic 和发布集合资格继续按原合同分别报告。

当前本批七类各 5 题，共 35 个正式资产，均已完成参考及代表负例校准。
前六类 30 题的实际校准范围见 [校准证据](../../experiments/benchmark_first_batch/CALIBRATION.md)。
五个优化任务的 36 个提交、108 个条件均完成封存核验，无待处理条件，见
[优化正式校准说明](../../experiments/benchmark_first_batch/optimization/FORMAL_CALIBRATION.md)
及[核验收据](../../experiments/benchmark_first_batch/optimization/formal_calibration_receipt.json)。
优化参考的 15 个条件全部通过；Flash 旧二分提交的 3 个 CPU-only equivalent 校准条件通过。
30 个负例的 90 个条件包含 63 个语义失败、5 个性能失败和 22 个通过条件，每个负例
至少一个条件被拒绝。负例按提交分为 24 个语义负例、5 个仅性能负例和 1 个混合负例。
metadata 准入计数本身不证明校准完成，执行状态以对应证据为准。

模型 pilot 的 14 个固定单元覆盖七类代表题及 `glm-5.3`、`glm-5.3-flash` 两个
同 family 的实际 endpoint。试跑正在进行，尝试、工具轨迹和成绩属于
[Agentic 证据](../../experiments/benchmark_first_batch/agentic/README.md)，不能由 metadata
或人工参考解校准推导 35 题整体模型通过率。
