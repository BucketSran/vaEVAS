# 维护题卡与任务定位

单文件题的新目标格式见[题包规范](../docs/task-package.md#单文件题的目标规范)：
直接编辑并交付 `/app/circuit.va`，题面使用 `Spec` 和 `Deliverable` 两个主段。
多文件工程按[交付约定](../docs/task-package.md#多文件工程的交付约定)保留实际布局，默认逐文件声明，确有需要时开放目录。
模块名按电路功能命名，公开 testbench 提供指标和公开用例的 PASS/FAIL；
终评材料与求解环境隔离，公开通过不代表整题通过。
本目录 INSTRUCTION.md 已按新规范更新，[阶段静态检查](../docs/evaluation.md#题包静态检查)已接入，实际题包和生成器仍待迁移；
模板更新不表示现有 R01 已完成格式统一。

先按[建设流程](../docs/evaluation.md#建设流程与完成标准)确认当前阶段。
功能族讨论与任务方向可以直接记在该族 README、任务清单和现有 issue 中；
已有清单不必为了使用模板再创建一套历史题卡。以下步骤用于确实需要新增或维护设计卡的工作。

1. 从总表和暂缓项确认未使用的全局 Case ID；编号不随分类变化，不回收旧编号。
2. 在 `catalog.json` 已登记的工程动作与电路家族下创建 `case-NNNN-purpose/`。
3. 复制本目录 [case.json](case.json) 和 [CASE.md](CASE.md) 为新目录的 `case.json` 与 `README.md`，替换占位信息。模板本身不参与题目计数。
4. 查已有来源与电路记录；复用相同 ID，缺少时再登记固定版本、实读范围和许可。没有选定电路时用空数组，不能编造资产。
5. 填写设计目标、原材料与新增要求、独立验收、待确认项。实现前可以另写明确标注的题面草案；正式任务建成后链接唯一有效题面。
6. 维护实际任务关联时按下方登记方式同步；从仓库根用 Python 3.11+ 运行 `python3 -B scripts/benchmark_workbench.py --write`，然后 `--check`。生成索引不用手工维护。

元数据中 `task_path`、`evidence_paths` 都相对仓库根目录；来源 ID 对应 `sources/<id>.md`，电路 ID 对应 `circuits/<id>.md`。`backend` 未选定时必须为 null，选定后写工具链及版本说明；具体数值设置保存在任务环境与证据中。

修改公开合同后递增设计版本并重新提交 review。待 review 不是实现失败；设计已认可也不是后端或 checker 已验证。接受本版设计时，填写对应 `reviewed_revision` 并在正文记下真实 reviewer、日期、范围及可用的提交引用。

如果用户只认可选题方向，在正文 Review 记录中写明认可范围，具体设计仍保持 `pending`，不填写 `reviewed_revision`。记录方向反馈本身不改变公开合同，无需递增设计版本。

阶段可用值：`source-screening`、`design-draft`、`implementation`、`calibration`、`model-trials`、`frozen`、`deferred`。设计 review 可用值：`pending`、`changes-requested`、`accepted`、`not-requested`。

上下文可用值：`bounded-work-unit`、`bounded-project`、`full-repository`。公开自测方式：`undecided`、`fixed-public-tests`、`fixed-connections-custom-probes`。即使尚未选自测形式，也应在正文写清拟交付物与终评边界。

## 从方向转成正式题包

按[英文 Agent 流程](../docs/agent-workflow.md#2-build-only-the-authorized-design-stage)执行当前授权阶段，
阶段材料与自动检查以[评测规则](../docs/evaluation.md#题包静态检查)为准。
从应用和初步行为依据开始，建立 gold 后再完善公开自测、终评、评分与英文 instruction；
早期允许明确的待定项，历史题的数值与运行记录不自动成为新题依据。
逐题按[checker 与终评设计流程](../docs/agent-workflow.md#design-public-checks-and-final-evaluation)
补齐现有验收对应表，定义预期、观测、公开与终评覆盖及校准计划，再完善题面。

按 [instruction 内容分工](../docs/task-package.md#单文件题的目标规范)填写 [INSTRUCTION](INSTRUCTION.md)。
按[行为说明与草稿边界](../docs/task-package.md#行为说明的详细程度与草稿边界)核对要求是否完整、重复能否合并、作者状态是否混入题面。
单文件题只复制尾段标记之间的正文，去掉标记和模板作者提示；草稿中的具名待定项按上述规则保留。
[固定尾段与参考材料约定](../docs/task-package.md#固定执行尾段与参考材料)中的机械规则由现有 lint 检查，内容完整性仍须 review。

批量建设按[复用步骤](../docs/agent-workflow.md#reuse-the-workflow-across-a-batch)推进，
人工参与点与默认短表见[审核分工](../docs/evaluation.md#人工介入与批量交付)。
详细对应表用于作者检查；代表题、实质例外和人工选定项再展开，不把逐题实现细节变成人工审批清单。
中文导读链接实际题包、英文题面、独立接口、公开工程与证据。
Agent 路径保留 `/app` 语义，人工导读的链接按仓库布局填写并核验。
保持求解者公开材料自足，不把完整规格另抄一份；参考解和 checker 用于最终审核。
时序题按[边界说明](../docs/task-package.md#时序边界与验收说明)检查事件与观察窗口，
成绩按[失败计零分、原因另记](../docs/evaluation.md#任务分数与失败原因)处理；待定数字仍可保留。

每轮交接在现有记录中给出当前阶段、范围与依据、本轮交付、实际完成结果和下一项依赖。
文档或检查仍在未合入的工作区时，链接其可见入口；后续工作不能据此声称 main 已采用。

## 登记已建设任务

`benchmark/material/draftbench/tasks.json` 保存当前 `vN-*`（N ≥ 2）任务的功能组与历史设计卡关联。
它与草稿批次内该范围的实际题包逐一对应；按题录取后关联正式位置。当前 R01 合同草稿另见批次入口，旧首批和早期 VA 题包留在 historyref，不加入 56 题分母。
R01 旧格式草稿已归档，不登记为已建设任务。后续采用其他任务命名时，先明确并适配登记范围。

| 字段 | 内容 |
| --- | --- |
| `function_groups` | 稳定组 ID 对应中文 `title` 和唯一审核编号 `review_id` |
| `tasks[].task_id` | 唯一任务目录名；参数场景不另登记 |
| `tasks[].title` | 总览中的中文题名 |
| `tasks[].function_group` | 一个主要电路功能组；跨组关联留在人工说明中 |
| `tasks[].case_ids` | 对应的历史设计卡，可多对多；无历史卡时填 `[]` |

类别和来源组直接读取各题 `task.toml`，不在登记表重复维护。每题须有 `instruction.md`、
`SOURCE.md` 和 `task.toml`；固定来源版本、许可和改编范围仍由 SOURCE 说明。
关联记录设计沿革，不表示旧卡合同与实际题包相同，也不改变设计认可或运行证据。

工具只生成计数、定位链接和设计卡的实现关联。工程价值、同源差异、输入/交付/checker 概述
和覆盖缺口保留为人工区域。`--check` 拒绝漏登记、重复 ID、失效文件、无效分类、卡片关联和过期索引；
它还按[阶段规则](../docs/evaluation.md#题包静态检查)检查新题包格式；不判断题目质量，不更新 #159，也不自动认可设计与校准结果。
