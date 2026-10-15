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

1. 从已认可方向中选一个样板，查同类现有工程题。文件分工参考[已有工程题](https://github.com/BucketSran/vaEVAS/tree/ff5d0fd9bc4dbeafe7fc91e233ad97880155a233/benchmark/tasks/v2-test-hysteresis)，英文题面从 [INSTRUCTION.md](INSTRUCTION.md)起草；历史题的文字和验收规则不自动成为新合同。
2. 按[题包规范](../docs/task-package.md#任务结构)独立编写公开 starter。建模题默认只给接口声明、参数和 TODO，特殊接口才补注释。instruction 引用它，说明工程目标、行为要求、修改范围与交付；公开运行的详细使用说明放在对应运行工具或公开 README 中。
3. Agent 先核对代表题公开材料的合同一致性并列出疑点，再把英文题面、独立接口、实际公开工程、交付伪代码和[验收方案](../docs/evaluation.md#验收方案与结果呈现)交人工审核。人工重点判断工程价值、工作边界、关键行为、交付与实验是否有解释力；尚待审核时如实记录，不称为已认可模板。
4. 代表题合同确认后，完成参考解和独立 checker，走通公开运行、参考交付和独立终评，完成必要的作者校准；再将相同文件分工复用到授权范围。新环境先验证一个题，避免批量发现环境依赖。
5. 按共用电路资产逐组完成建设与校准，检查生成源与题包一致，逐组交付人工 review。新规范的静态检查仍待适配；工具可用后确认其覆盖并记录实际结果。每组说明新增工作、同源区别与剩余问题；源码、运行结果和未决问题回到已有任务清单与校准记录。

人工 review 使用真实题包和简短中文导读。导读写在功能族现有任务清单或说明中，
说明场景、材料、代码大体思路、关键行为、交付伪代码与未决问题，并链接英文题面、
独立接口和公开工程。保持求解者公开材料自足，不把完整规格另抄一份；参考解和 checker 用于最终审核。

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
它不判断题目质量或新题包格式，不更新 #159，也不自动认可设计与校准结果。
