# Verilog-A Benchmark

本 benchmark 评估模型与智能体能否用 Verilog-A 完成电路工程任务。
任务采用 Harbor 格式，交付物由经过作者校准的独立 checker 验收。
纯代码理解和技术问答不作为任务。

## 从哪里开始

| 入口 | 内容 |
| --- | --- |
| [workbench/](workbench/README.md) | 按电路功能审核、收集材料和设计题目，保存共同定义与候选 |
| [tasks/](tasks/) | 题目包及题集清单，包含输入、参考解和独立验收 |
| [checkers/](checkers/) | 多道题共用的评分代码，随题打包的副本由建设脚本维护 |
| [reference/](reference/README.md) | 保持原貌的历史 benchmark 与原始 Verilog-A 资料 |

原始资料的来源与使用范围见 `reference/` 的说明。实验协议、结果与证据由
[experiments/](../experiments/README.md)维护；仿真执行调度属于独立的 circuit harness。

## 当前审核

[56 题总览](workbench/TASKS.md)合并两批已建设任务：37 题与后续 19 题，
按五类工程动作和电路功能列出输入、交付、checker 思路、同源变体与覆盖缺口。
每道题仅计一次；历史初筛、旧七类题集和设计卡不额外加入这 56 题。

当前先整理 main 的材料、工作分支和待完成事项，暂不开始实际题目设计或模型实验。
材料集合、分支状态和后续整理事项见[当前盘点](workbench/DISCUSSION.md#当前材料与待整理事项)。
电路功能与场景审核仍以 [#159](https://github.com/BucketSran/vaEVAS/issues/159) 为入口，
例如 [R01 采样与多通道读出](workbench/circuits/r01-sampling/README.md)。
R01 的 20 道新题草稿、参考解、checker 和旧格式运行记录仍保留在本地工作区，尚未进入 main，
不加入上述 56 题。新题包规范已确认，实际题包迁移、代表题合同及验收方案审核仍待完成；
历史作者校准不能替代新规范的验收或人工设计认可。
原有 18 张设计卡与 62 个迁移来源候选留在工作区供追溯，不与题量相加。

<a id="目标与边界"></a>
<a id="评测方式与题目建设"></a>
<a id="开源复现与结果报告"></a>

## 设计与评测约定

- [设计目标与选题判断](workbench/docs/design.md)：工程价值、电压域范围、上下文层次和来源。
- [五类任务定义](workbench/docs/task-types.md)：输入、交付物、修改权限与独立验收。
- [评测与复现原则](workbench/docs/evaluation.md)：Agentic 与 One-shot、固定后端、作者校准、环境缺陷与成绩报告。

电路功能和五类工程动作通过总览与任务元数据关联。共享电路不因派生出多个任务而失去同源关系。
设计认可、作者校准、运行适配和正式发布分别记录；合入 main 不自动代表所有后端均可复现。

## 任务结构

### 单文件题的目标规范

2026-10-14 题包规范讨论已确认，采用 analog-design-bench 的原位编辑与交付方式：
仓库中的 `environment/starter/circuit.va` 进入环境后成为 `/app/circuit.va`。
该文件提供固定接口和起始内容，求解者直接编辑它，最终也收集同一文件。
`task.toml` 明确声明 `artifacts = ["/app/circuit.va"]`。多文件工程的约定后续单独细化。

英文 instruction 开头简述本题工程工作，以 `Spec`、`Deliverable` 两个主段组织。
`Spec` 说明本题规格与实验条件，`Deliverable` 指向实际工作文件并给出公开测试入口；
必要的 Constraints 用短段说明。接口声明仍在起始文件中，题面引用而不重复。

文件名统一为 `circuit.va`，内部顶层模块使用电路功能名，例如 `track_hold`、
`interleaved_sampler`；新题不额外拼入题号前缀。改编已有真实工程时保留其原模块名和接口。

从头建模题的 starter 只提供模块、端口、参数声明和 TODO，不预置内部节点、状态变量或算法。
默认不添加逐端口、逐参数说明。参数声明给出默认值与范围，`Spec` 使用信号和参数名说明行为与单位；
只有浮动参考域、含义不直观的引脚等特殊接口关系才补短注释。
有限采集题只需一条 TODO，来源事实见[analogbench starter 核对](workbench/sources/analog-task-package.md)。
扩展题提供正常工程，修复题提供故障工程，保留已有实现。

`testbench/` 提供可运行的公开测试和分析入口，输出指标与公开条件的 PASS/FAIL。
按任务需要提供仿真台架和分析入口。短题在 instruction 中给一条运行命令即可；
多台架、特殊连接或输出解释较复杂时，增加英文 README，说明运行方法、公开覆盖和输出含义，
不重复完整 `Spec`。
公开反馈判断候选在该公开用例中是否满足任务要求，不等同于整题通过；
测量题判断的是测量与报告是否正确，不把被测电路本身性能合格作为仪器通过的前提。
终评使用独立条件，参考解与终评材料继续与求解环境隔离。

`tests/test.sh` 是评分入口，`tests/verify.py` 执行或调用独立验收与评分。
仿真台架按需放入 `tests/benches/`，参数用例、辅助代码和 verifier Dockerfile 按实际需要添加。
作者准备的[校准样本](../GLOSSARY.md#校准样本)按需放入 `tests/fixtures/`，
不强求每题准备相同数量的样本。作者校准工具把样本逐个作为候选交给同一 checker，
验证正确实现被接受、指定错误被识别；样本应关联预期结论和所检要求，运行异常另记。
正式终评只评分求解者提交，不将这些样本计入该次成绩或 benchmark 题量。

参考解按人工 review 需要注释关键电路机制、状态保持和边界处理，不要求逐行注释；
简单实现可以没有额外说明。建模 starter 的最小注释规则不限制参考解。

当前开发阶段保留 `SOURCE.md`，作为作者与 reviewer 查看来源、改编及同源关系的入口，
链接已有 workbench 材料。它是本项目的作者记录，不是 Harbor 要求，也不进入求解环境。

完成真实运行后，在 `results/reference.json` 保存参考解的指标、结论与版本身份，
在 `results/calibration.json` 保存独立 checker 的正确与错误对照校准摘要。
原始波形和大日志留在已有运行记录中；这些 JSON 是作者证据，不作为候选的期望答案，
也不进入求解环境。合同或制品变化后，保留结果所对应的版本，不能把旧运行改记为新版本证据。

结果表使用 `Specification | Limit | Value | Pass/Fail`，从与 JSON 相同的结构化判定结果生成，
完整展示验收条件。先审规格、台架实验、测量定义和判定标准之间的对应，再实现 checker 并校准；
具体规则见[验收方案与结果呈现](workbench/docs/evaluation.md#验收方案与结果呈现)。

单个可修改文件的题包采用以下目标结构。`environment/starter/` 的公开材料进入 `/app/`，
参考解和独立终评材料留在求解环境之外；下列结构不要求短规格额外拆文件。

```text
benchmark/tasks/<task-id>/
├── instruction.md
├── task.toml
├── SOURCE.md
├── environment/
│   ├── Dockerfile
│   └── starter/
│       ├── circuit.va
│       └── testbench/          # 公开台架与分析入口，README 按需
├── solution/
│   ├── circuit.va
│   └── solve.sh
├── tests/
│   ├── test.sh
│   ├── verify.py
│   ├── benches/               # 按需
│   └── fixtures/              # 按需，作者校准样本
└── results/
    ├── reference.json
    └── calibration.json
```

上述是已确认的目标规范，本次同步规范与英文起草模板。现有任务和本地 R01 草稿仍按原工程保留，
生成器、格式检查和实际题包尚待迁移。旧格式检查通过不能作为已与 analogbench 统一的证据；
实际迁移和受影响的校准完成前，继续使用各任务原有运行合同。
已读取的格式参照为 [analogbench MUX 题包](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-analog-input-mux-8to1-pvt)。

### 作者目录与记录

新题的 `instruction.md` 用英文说明工程起点、行为要求、可修改范围与交付。接口声明与参数定义放在公开起始工程文件中，题面引用该文件，starter 注释遵循上面的目标规范。短行为规格可以直接放在题面；已有工程规格可以引用，内容长或需要共用时再拆文件。`task.toml` 配置任务，`SOURCE.md` 记录来源与改编。
`environment/` 提供运行环境与公开输入，`solution/` 保存参考解，`tests/` 执行独立评分，`results/` 保存版本对应的作者运行摘要。
评分按 Harbor 约定输出 `/logs/verifier/reward.txt` 或 `reward.json`，详见
[Harbor 任务格式](https://docs.harborframework.com/tasks/overview)。
从功能族讨论到题包交付的顺序见[建设流程](workbench/docs/evaluation.md#建设流程与完成标准)，
英文起草模板与样板核对见[题包建设](workbench/templates/README.md#从方向转成正式题包)。
题集清单作为文件放在 `tasks/` 根下；现有旧七类清单及其历史身份见[路径对照](workbench/history/README.md#首批题集配置的位置)。

<a id="从开发问题积累候选"></a>
<a id="共享评分程序"></a>
<a id="环境与结果"></a>

## 维护与历史

开发中发现的可复用问题进入[候选登记](workbench/CANDIDATES.md)，先记录触发条件、独立预期与证据，
不自动创建题目或增加评分分母。题卡索引由 `python3 -B scripts/benchmark_workbench.py --check` 检查。
共享 checker 的副本同步、校准与环境说明见[评分实现](workbench/docs/evaluation.md#共享评分程序)。

[历史题集与建设记录](workbench/history/README.md)保留初筛、旧七类和后续两批的来源及实验入口；
[历史设计稿](workbench/examples/README.md)保留早期设想，包括已不属于当前五类的方向。
[总体议题 #72](https://github.com/BucketSran/vaEVAS/issues/72)和[分类议题 #107](https://github.com/BucketSran/vaEVAS/issues/107)用于追溯建设讨论。
