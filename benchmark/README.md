# Verilog-A Benchmark

本模块评估提交的 Verilog-A 模型是否完成指定任务。
任务格式已确定：使用 **Harbor 原生格式**。

当前有 6 个来自真实资产的内部初筛任务，覆盖逻辑对照、SAR 握手、ZOOM 时序、
增益校准、动态 VCO 和带负载运放。题目清单、校准和 GLM/Codex 运行协议见
[能力初筛说明](../experiments/va_screen/README.md)。它们尚不是正式 benchmark 发布版。
[reference/](reference/README.md) 保存历史 vaBench 发布包（v1 完整、v4 最新快照+文档），
以及按来源和功能整理的[原始 Verilog-A 资料](reference/veriloga/README.md)。
原始资料分为课题组工程模型与 Cadence 安装库模型，仅供内部研究，不对外分发。
另有一个仓库自有的候选修复题：[积分三角波振荡器](tasks/va07-triangle-repair/instruction.md)。
它检查双向事件导致的边界反复换向，单独校准，不加入原六题的初筛成绩。
任务位于 `tasks/`；每题 `SOURCE.md` 说明原始资产和必要改编，原始源码保持不变。

## 从开发问题积累候选

[CANDIDATES.md](CANDIDATES.md) 记录开发中发现的问题及可能形成的建模任务。
先保留最小触发条件、独立预期、实际失败和证据；后续再集中做题目改造、评分和环境适配。
记录候选不自动创建 Harbor 目录，不增加正式题目或评分分母。
已经存在的振荡器题目是候选原型，仍需按登记表完成正式改造审阅。
开发、验证和 review 入口都执行这项记录规则，具体步骤见
[协作流程](../CONTRIBUTING.md#development-bench-candidates)。

## 任务结构

任务放在 `benchmark/tasks/<task-id>/`。每个任务使用以下结构：

```text
benchmark/tasks/<task-id>/
├── instruction.md
├── task.toml
├── environment/
│   └── Dockerfile
├── solution/
│   └── solve.sh
└── tests/
    └── test.sh
```

| 文件 | 用途 |
| --- | --- |
| `instruction.md` | 说明建模要求、可用输入和完成条件 |
| `task.toml` | 配置任务信息、运行资源和时间限制 |
| `environment/Dockerfile` | 建立任务使用的工具与输入环境 |
| `solution/solve.sh` | 执行参考解，用于验证任务和评分程序 |
| `tests/test.sh` | 检查提交的模型，并输出评分结果 |

本项目的任务随任务保存参考解。Harbor 的结构和环境选项见
[官方任务说明](https://docs.harborframework.com/core-concepts/tasks/overview)。
评分程序按 Harbor 约定写入 `/logs/verifier/reward.txt`，或使用其支持的 `reward.json` 格式。

## 共享评分程序

[checkers/spectre_waveform.py](checkers/spectre_waveform.py) 是六题共用的评分源码。
[任务生成器](../experiments/va_screen/build_tasks.py)将它复制到每题的 `tests/verify.py`；
任务运行时执行该副本，`tests/cases.json` 保存各题的网表、独立期望值与容差。

修改共享源后，需要同步受影响的执行副本，并重做其参考解和错误版本校准。
生成器会重建全部六题文件，运行前应保留正在修改的任务。提交前使用
[身份检查](../experiments/va_screen/README.md#身份与再校准)确认源、副本及校准记录一致。
校准通过证明这些已测条件，不能证明评分程序覆盖任意错误实现。

[checkers/triangle_oscillator.py](checkers/triangle_oscillator.py) 单独负责振荡器修复题。
它使用正速度的分段解析积分和三角波折返关系；固定题目配置与错误版本校准见
[来源和验证边界](tasks/va07-triangle-repair/SOURCE.md)。无需 Spectre 的检查器回归：

```sh
python3 -B -m unittest discover -s experiments/backends/dvs2-spectre-validation -p test_triangle_oscillator.py -v
```

## 环境与结果

每个任务在自己的 `environment/` 中声明运行环境。
当前使用固定 digest 的 Python 基础镜像与远端 Spectre verifier；
任务镜像本身不包含商业仿真器，运行时必须按初筛说明指定 verifier。
镜像应记录依赖版本和构建方法；执行记录应保存实际使用的镜像身份。
完整运行日志与临时输出放在 Git 忽略的 `runs/` 中。

Benchmark 评分与 [EVAS 正确性验证](../evas/validation/README.md)分别维护和报告。
EVAS 的构建与运行方法见 [仿真器说明](../evas/README.md)。
