# Benchmark 核心设计文档

这里保存当前采用的设计判断及其理由，供项目成员和电路领域同行阅读。先读
[设计目标与选题判断](design.md)，再按需要查看任务定义和评测规则。

| 文档 | 回答的问题 |
| --- | --- |
| [设计目标与选题判断](design.md) | 为什么建设这个 benchmark？哪些工作值得考察？目前希望同行帮助判断什么？ |
| [五类工程任务](task-types.md) | 每类给定什么、交付什么、允许修改什么、怎样验收？类别之间怎样区分？ |
| [评测与复现原则](evaluation.md) | Agent 如何解题？如何选择后端、建立 checker、处理环境缺陷和报告成绩？ |

## 各类材料放在哪里

| 位置 | 保存内容 |
| --- | --- |
| `benchmark/docs/` | 已采用的共同定义、设计理由和仍待讨论的核心问题 |
| [research/](../research/README.md) | 论文、技术资料和开源工程的阅读结果、适用范围与证据 |
| [workbench/](../workbench/README.md) | 每个 Case 的来源、电路、拟定形式、规格草案、checker 方案与 review 状态 |
| [tasks/](../README.md#任务结构) | 可执行任务、参考解和评分入口，资格由各题证据说明 |
| GitHub Issues | 工作范围、依赖、验收条件和推进状态 |
| [实验入口](../../experiments/README.md) | 已运行实验的协议、结果和证据，不用候选数量代替成绩 |

[Issue #72](https://github.com/BucketSran/vaEVAS/issues/72) 负责总体建设与阶段入口；
[Issue #107](https://github.com/BucketSran/vaEVAS/issues/107) 负责五类定义及代表题的验收设计。
共享执行工具的可靠性由
[circuit-harness #5](https://github.com/BucketSran/circuit-harness/issues/5) 跟进。

文档正文表达当前方案。改变共同定义时，更新对应文档，并在现有 issue 中说明理由和证据。
逐题进度回到题卡，执行过程回到实验记录；历史分类、旧成绩和来源身份保留原记录。
候选方向、可运行任务、已校准任务及正式发布任务分别说明，不能相互代替。
