# vaEVAS

vaEVAS 是面向 Verilog-A 建模与评测的研究项目，包含 **benchmark** 和 **EVAS 电压域仿真器**。
benchmark 组织建模任务与验收要求，EVAS 为支持范围内的模型提供仿真能力，
便于在同一工作区开展模型编写、仿真和结果检查。

## Benchmark

benchmark 用于评估 Verilog-A 建模能力：给定模型规格，检查所编写的模型是否满足任务要求。
建设内容包括题目、运行环境、参考解和验收材料，采用 Harbor 任务格式。

**当前状态：**[benchmark/](benchmark/README.md) 已建立占位入口，任务格式已确定为 Harbor 原生格式。
旧 vaBench 任务集尚未迁入。任务加入后放在 `benchmark/tasks/`，共享镜像构建文件放在 `benchmark/containers/`。

## EVAS 仿真器

EVAS 将 Verilog-A 中的电压贡献转为方程，由 Rust 内核联立求解节点电压。
它面向以电压关系描述的行为模型，目前在限定范围内提供：

- **静态求解**：线性关系、多项式非线性反馈及稠密/稀疏矩阵求解。
- **瞬态与事件**：随时间推进输入和状态，处理 `cross`、固定 `timer`、采样与复位。
- **动态算子**：`transition`、`absdelay`、`slew`，以及受限的积分、微分和滤波关系。

输入由 `.va` 模型和 JSON manifest 组成；manifest 指定实例、节点连接和输入刺激。
当前不支持电流贡献和器件级电路网表求解，各算子的参数与组合限制见[能力表](evas/docs/CAPABILITIES.md)。

## 快速开始

需要 Python 3.10+ 和 Rust/Cargo。从源码构建并运行一个电压贡献求和示例：

```sh
git clone https://github.com/BucketSran/vaEVAS.git
cd vaEVAS
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_sum.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

[示例 manifest](evas/examples/static_sum.json)定义三组输入，所引用的
[Verilog-A 模型](evas/validation/cases/n_v1_02/dut.va)将三条电压贡献相加。
命令输出 JSON，`solutions` 中的电压按 `nodes` 顺序排列；三组输入的 `out` 电压约为
`0.225 V`、`1.825 V` 和 `-0.325 V`。

更多非线性与瞬态示例见 [EVAS 使用说明](evas/README.md#构建与运行)。
benchmark 的运行入口将随任务集补齐，目前可先运行 EVAS 示例。

## 验证与实验

[独立验证集](evas/validation/README.md)使用共同模型和判据检查仿真器行为，
开发回归另外覆盖解析答案、语义不变性、失败后重试及算子组合。
它们与 benchmark 建模任务的评测成绩分别报告。

[实验记录](experiments/README.md)提供当前 EVAS 的验证结果、Spectre 等后端的历史对照和复现入口。
各轮结果绑定实际源码、输入和检查器；有限测试的通过范围与剩余验证限制在对应记录中说明。
main 保留持续维护的工具与支撑公开结论的精简证据；已结束的审查和阶段报告从固定历史提交查阅。
具体资产去向见[实验索引](experiments/README.md#现有目录如何处理)，保留规则见[贡献指南](CONTRIBUTING.md#main-branch-contents)。

## 仓库导航

| 目录 | 内容 |
| --- | --- |
| [benchmark/](benchmark/README.md) | Harbor 格式的任务、参考解、评分程序与运行环境入口 |
| [evas/](evas/README.md) | 仿真器源码、示例与开发测试 |
| [evas/docs/](evas/docs/README.md) | 数学原理、设计与支持边界 |
| [evas/validation/](evas/validation/README.md) | 独立测试模型、契约与检查器 |
| [experiments/](experiments/README.md) | 实验协议、执行收据与整理结果 |

开发与文档维护方法见[贡献指南](CONTRIBUTING.md)。
