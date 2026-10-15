# 题包格式与验收约定

本 benchmark 评估模型与智能体能否用 Verilog-A 完成电路工程任务。
任务采用 Harbor 格式，交付物由经过作者校准的独立 checker 验收。
纯代码理解和技术问答不作为任务。

本文保留此前已确认的题包分工。目录录取规则与当前状态见
[benchmark 入口](../../../README.md)。正式题仅在 `benchmark/tasks/`；当前草稿在 `material/draftbench/batches/<batch-id>/tasks/`，早期题包在 `material/historyref/tasks/`。
下方关于 `SOURCE.md`、参考解、checker 和结果记录的要求用于完成题包，草稿不因此自动录取。

## 设计与评测约定

- [设计目标与选题判断](design.md)：工程价值、电压域范围、上下文层次和来源。
- [五类任务定义](task-types.md)：输入、交付物、修改权限与独立验收。
- [评测与复现原则](evaluation.md)：Agentic 与 One-shot、固定后端、作者校准、环境缺陷与成绩报告。

电路功能和五类工程动作通过总览与任务元数据关联。共享电路不因派生出多个任务而失去同源关系。
设计认可、作者校准、运行适配和正式发布分别记录；合入 main 不自动代表所有后端均可复现。

## 任务结构

### 单文件题的目标规范

2026-10-14 题包规范讨论已确认，采用 analog-design-bench 的原位编辑与交付方式：
仓库中的 `environment/starter/circuit.va` 进入环境后成为 `/app/circuit.va`。
该文件提供固定接口和起始内容，求解者直接编辑它，最终也收集同一文件。
`task.toml` 明确声明 `artifacts = ["/app/circuit.va"]`。多文件工程见下方[交付约定](#多文件工程的交付约定)。

英文 instruction 开头简述本题工程工作，以 `Spec`、`Deliverable` 两个主段组织。
`Spec` 说明本题规格与实验条件，`Deliverable` 指向实际工作文件并给出公开测试入口；
必要的 Constraints 用短段说明。接口声明仍在起始文件中，题面引用而不重复。

文件名统一为 `circuit.va`，内部顶层模块使用电路功能名，例如 `track_hold`、
`interleaved_sampler`；新题不额外拼入题号前缀。改编已有真实工程时保留其原模块名和接口。

从头建模题的 starter 只提供模块、端口、参数声明和 TODO，不预置内部节点、状态变量或算法。
默认不添加逐端口、逐参数说明。参数声明给出默认值与范围，`Spec` 使用信号和参数名说明行为与单位；
只有浮动参考域、含义不直观的引脚等特殊接口关系才补短注释。
有限采集题只需一条 TODO，来源事实见[analogbench starter 核对](../sources/analog-task-package.md)。
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
作者准备的[校准样本](../../../../GLOSSARY.md#校准样本)按需放入 `tests/fixtures/`，
不强求每题准备相同数量的样本。作者校准工具把样本逐个作为候选交给同一 checker，
验证正确实现被接受、指定错误被识别；样本应关联预期结论和所检要求，运行异常另记。
正式终评只评分求解者提交，不将这些样本计入该次成绩或 benchmark 题量。

参考解按人工 review 需要注释关键电路机制、状态保持和边界处理，不要求逐行注释；
简单实现可以没有额外说明。建模 starter 的最小注释规则不限制参考解。

当前开发阶段保留 `SOURCE.md`，作为作者与 reviewer 查看来源、改编及同源关系的入口，
链接已有草稿工作区材料。它是本项目的作者记录，不是 Harbor 要求，也不进入求解环境。

完成真实运行后，在 `results/reference.json` 保存参考解的指标、结论与版本身份，
在 `results/calibration.json` 保存独立 checker 的正确与错误对照校准摘要。
原始波形和大日志留在已有运行记录中；这些 JSON 是作者证据，不作为候选的期望答案，
也不进入求解环境。合同或制品变化后，保留结果所对应的版本，不能把旧运行改记为新版本证据。

结果表使用 `Specification | Limit | Value | Pass/Fail`，从与 JSON 相同的结构化判定结果生成，
完整展示验收条件。先审规格、台架实验、测量定义和判定标准之间的对应，再实现 checker 并校准；
具体规则见[验收方案与结果呈现](evaluation.md#验收方案与结果呈现)。

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

上述是已确认的目标规范。56 个保留题包仍使用原工程合同；当前 R01 批次只有有限采集的合同草稿，
尚未接入完整环境、参考解与终评。题包生成器、格式检查和实际题包仍需按规范适配。
目录搬迁或旧格式检查通过不能作为已与 analogbench 统一的证据；
完成实际转换和受影响的校准前，历史结果继续按原运行合同解释。
已读取的格式参照为 [analogbench MUX 题包](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-analog-input-mux-8to1-pvt)。

### 多文件工程的交付约定

2026-10-15 已确认：沿用 Harbor 外层结构，在 `/app/` 原位修改并自动收集交付物。
默认逐文件声明，确有自由拆分模块或维护工程目录的需要时，才开放指定目录。
输入是多文件工程，不代表交付也必须有多个文件；例如在完整系统中补一个模块，可以只交付该模块。

`environment/starter/` 按相对路径复制到 `/app/`。新建 VA 工程可使用下列布局，
少量文件可以平铺，子目录按需增加；改编真实工程时保留原文件名、目录和入口，不强制改名为 `circuit.va`。

```text
environment/starter/
├── circuit.va             # 新建 VA 工程的顶层入口
├── modules/               # 按需拆分模块
│   ├── sampler.va
│   └── controller.va
├── design_params.inc      # 需要独立参数文件时才提供
└── testbench/              # 公开测试与分析入口
```

接口声明留在对应起始源码中。建模、扩展和修复的起始内容继续按上方分工提供。
工程入口、依赖或运行方法较复杂时，增加英文 README，避免把完整规格另抄一份。
`solution/` 按相同相对路径保存参考交付文件，由 `solve.sh` 安装到 `/app/` 对应位置；
固定依赖由环境提供。`tests/`、`SOURCE.md` 和 `results/` 的职责与单文件题相同。

英文 instruction 仍用 `Spec` 与 `Deliverable`。`Deliverable` 明确交付路径和可修改范围，
必要的接口或架构限制放在 `Spec` 的 `Constraints` 中。文件与模块名采用工程本身的名称。

| 内容 | 修改与交付约定 |
| --- | --- |
| 待完成或修改的模块 | 逐文件列出；允许整体重写，仍须满足规定的接口、行为和模块职责 |
| 系统连接、设计参数、源文件清单 | 按工程工作决定是否可改，明确列入范围；文件可见不代表可修改 |
| 固定依赖、官方公开测试、评分材料 | 保持作者版本，不作为求解者可修改的交付物 |
| 新增辅助模块 | 仅在题目明确开放的目录中新增，说明如何被工程加载并纳入交付 |
| 自定义实验文件 | 按题允许用于自测，是否属于交付物另行声明 |

当任务是开发 VA 测试或测量模块时，该模块属于可修改的交付物；用来验收它的外部测试保持固定。
不能仅凭文件名或目录名含有 testbench 就把它视为固定材料。

`task.toml` 的 `artifacts` 与公开交付范围保持一致。指定文件交付时，列出每个完整路径，
例如 `/app/circuit.va` 与 `/app/modules/sampler.va`。开放目录时，声明目录路径，
并说明允许新增、删除和重命名哪些文件，以及必须保留的入口与接口。
目录中含有固定材料时，须将其与可交付部分区分，不能因收集目录而允许覆盖固定材料。
交付源码所需的新依赖也必须处于声明的收集范围内。

求解者保存工作文件即可，不要求 Git 提交、打包或手写 patch。结束时收集声明范围的当前内容，
包括允许的新文件，不以是否执行 `git add` 判断；未声明的临时实验、波形和缓存不作为交付物。
运行器可生成差分供 review，但差分不能替代实际交付文件。

终评在独立环境中恢复固定工程基线，再装入声明的交付物。开放目录交付时，
需要保留合同允许的删除与重命名结果，不能让单纯覆盖复制把已删除的文件恢复回来。
固定材料不得被候选覆盖，收集遗漏应与候选本身缺少依赖分别诊断。
这些是运行适配的要求，当前文档更新不表示收集、恢复或完整 Harbor 流程已经验证。

来源分工见 [analogbench 题包核对](../sources/analog-task-package.md#多文件约定讨论的补查2026-10-15)
和 [CVDP heavy 多文件核对](../sources/cvdp-heavy-multifile.md)。
[Harbor artifacts](https://docs.harborframework.com/tasks/artifacts)支持文件或目录收集，
[独立 verifier](https://docs.harborframework.com/tasks/separate-verifier)支持重新建立评分环境。
默认逐文件声明、修改权限与目录恢复要求是本项目确认的约定，不是对所有 CVDP heavy 题目的描述。

### 作者目录与记录

新题的 `instruction.md` 用英文说明工程起点、行为要求、可修改范围与交付。接口声明与参数定义放在公开起始工程文件中，题面引用该文件，starter 注释遵循上面的目标规范。短行为规格可以直接放在题面；已有工程规格可以引用，内容长或需要共用时再拆文件。`task.toml` 配置任务，`SOURCE.md` 记录来源与改编。
`environment/` 提供运行环境与公开输入，`solution/` 保存参考解，`tests/` 执行独立评分，`results/` 保存版本对应的作者运行摘要。
评分按 Harbor 约定输出 `/logs/verifier/reward.txt` 或 `reward.json`，详见
[Harbor 任务格式](https://docs.harborframework.com/tasks/overview)。
从功能族讨论到题包交付的顺序见[建设流程](evaluation.md#建设流程与完成标准)，
英文起草模板与样板核对见[题包建设](../templates/README.md#从方向转成正式题包)。
正式题集的 `benchmark.toml` 与 `defaults.toml` 放在 `benchmark/tasks/` 根下；
旧七类清单归入历史区，其原身份见[路径对照](../history/README.md#首批题集配置的位置)。

<a id="从开发问题积累候选"></a>
<a id="共享评分程序"></a>
<a id="环境与结果"></a>

## 维护与历史

开发中发现的可复用问题进入[候选登记](../CANDIDATES.md)，先记录触发条件、独立预期与证据，
不自动创建题目或增加评分分母。`python3 -B scripts/benchmark_workbench.py --check` 检查历史题卡、
现有 `vN-*`（N ≥ 2）任务登记与生成索引；不证明题包符合新格式。
共享 checker 的副本同步、校准与环境说明见[评分实现](evaluation.md#共享评分程序)。

[历史题集与建设记录](../history/README.md)保留初筛、旧七类和后续两批的来源及实验入口；
[历史设计稿](../examples/README.md)保留早期设想，包括已不属于当前五类的方向。
[总体议题 #72](https://github.com/BucketSran/vaEVAS/issues/72)和[分类议题 #107](https://github.com/BucketSran/vaEVAS/issues/107)用于追溯建设讨论。
