# Verilog-A benchmark

本 benchmark 评估用 Verilog-A 完成电路建模、集成、修复与测试工作的能力。
`tasks/` 只收录本版明确通过人工题目审核、完成题包与必要作者校准的题目。
目录中有参考解或曾经跑通仿真，不代表题目已经审核通过。

## 从哪里开始

```text
benchmark/
├── README.md
├── tasks/
│   ├── defaults.toml
│   ├── benchmark.toml
│   └── <reviewed-task>/
└── material/
    ├── historyref/
    └── draftbench/
```

| 入口 | 内容 |
| --- | --- |
| [tasks/benchmark.toml](tasks/benchmark.toml) | 正式题集的唯一清单，列出已确认题目的 ID 与顺序 |
| [tasks/defaults.toml](tasks/defaults.toml) | 共用环境默认值，具体任务可以覆盖 |
| [material/draftbench/](material/draftbench/README.md) | 电路资产、选题讨论、设计批次与待审核题包 |
| [material/historyref/](material/historyref/README.md) | 原始 benchmark、外部来源和历史建设源码 |

2026-10-15，正式清单为空，状态为 `draft`。草稿区按[三批](material/draftbench/batches/README.md)保存两批 56 个实现和 1 个 R01 合同草稿，共 57 个题包。
更早的 41 个题包保存为[历史材料](material/historyref/tasks/README.md)。这些资产均未获得本版完整题目审核认可。
现有 56 题的功能覆盖见[草稿总览](material/draftbench/TASKS.md)，R01 的审核入口见
[有限采集建模](material/draftbench/circuits/r01-sampling/module/basic/README.md#有限采集建模题合同审核)。
这次整理不改变这些题目的原行为要求、评分判据或历史实验结论。

## 一个题包包括什么

题面、公开起始工程、参考解、checker 和作者结果共同构成题目资产，放在同一题包内。
checker 由该题的规格与实验决定，正式题不能依赖仓库外层的评分源码目录。
需要复用辅助逻辑时，也随题保存，并对该题的版本与校准负责。

```text
<task>/
├── instruction.md
├── task.toml
├── SOURCE.md
├── environment/
│   ├── Dockerfile
│   └── starter/
│       ├── circuit.va
│       └── testbench/
├── solution/
│   ├── circuit.va
│   └── solve.sh
├── tests/
│   ├── test.sh
│   ├── verify.py
│   ├── benches/       # 按需
│   └── fixtures/      # 按需
└── results/
    ├── reference.json
    └── calibration.json
```

单文件题在环境中原位编辑并提交 `/app/circuit.va`，英文 instruction 使用 `Spec` 和 `Deliverable`，
接口放在 starter 中。此前确认的完整分工见[题包约定](material/draftbench/docs/task-package.md#任务结构)。
多文件工程保留实际布局，在 `/app/` 原位修改，默认逐文件声明交付，确有需要时开放指定目录；
详见[多文件交付约定](material/draftbench/docs/task-package.md#多文件工程的交付约定)。
草稿中的旧格式继续保留，规范确认或目录迁移不表示格式迁移已完成。

## 从草稿进入正式题集

先在 `material/draftbench/batches/<batch-id>/tasks/` 按批次设计与审核，批次 README 保留进度与审核记录。
代表题合同与验收方案确认后，完成实现与作者校准，
再做最终人工题目 review。本版题包通过后移入 `tasks/<task-id>/`，在 `task.toml` 记录
`metadata.review_status = "accepted"`，并在 `SOURCE.md` 保留对应的人工审核记录。
同时把题目加入 `benchmark.toml`，原批次保留审核结论及正式题包链接，不另存有效副本。
同批未通过的题目继续留在草稿区。录取时核对 `defaults.toml`，共用设置变化时再修改；
题目特有设置放在自己的 `task.toml`。格式检查不能代替人工认可。
具体流程见[建设流程](material/draftbench/docs/evaluation.md#建设流程与完成标准)与
[批次管理](material/draftbench/docs/evaluation.md#按批次管理与逐题录取)。现有草稿已按批次存放，历史题包单独保留。

运行 `python3 -B scripts/benchmark_workbench.py --check` 检查草稿登记、生成索引和正式清单。
新题包另按[建设阶段](material/draftbench/docs/evaluation.md#题包静态检查)检查公开合同、实现文件和作者结果的基本结构。
检查拒绝正式目录与清单不一致、缺少题包文件或尚未标记审核通过的题目；不执行仿真，也不判断工程价值或认证人工审核。
模型实验与发布按相应授权推进。

`defaults.toml` 与 `benchmark.toml` 的文件分工参考 analog-design-bench 的
[默认配置](https://github.com/Arcadia-1/analog-design-bench/blob/main/tasks/defaults.toml)和
[题集清单](https://github.com/Arcadia-1/analog-design-bench/blob/main/tasks/benchmark.toml)。
当前默认值只建立配置入口，不表示 Harbor 环境、许可证访问或任意后端已经验证；这些由实际题包接入并校准。
