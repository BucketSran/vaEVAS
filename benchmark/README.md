# Verilog-A Benchmark

本模块评估提交的 Verilog-A 模型是否完成指定任务。
任务格式已确定：使用 **Harbor 原生格式**。

当前目录提供占位说明。旧 vaBench 任务尚未迁入，尚无可运行任务或共享镜像。

## 任务结构

任务加入后，放在 `benchmark/tasks/<task-id>/`。每个任务使用以下结构：

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

## 环境与结果

每个任务在自己的 `environment/` 中声明运行环境。
任务共用的镜像构建文件在实际加入时放入 `benchmark/containers/`。
镜像应记录依赖版本和构建方法；执行记录应保存实际使用的镜像身份。
完整运行日志与临时输出放在 Git 忽略的 `runs/` 中。

Benchmark 评分与 [EVAS 正确性验证](../evas/validation/README.md)分别维护和报告。
EVAS 的构建与运行方法见 [仿真器说明](../evas/README.md)。
