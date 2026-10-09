# EVAS 文档

先看 [能力概览](CAPABILITIES.md)，判断模型是否在支持范围内。
需要安装或运行时，从 [EVAS 使用说明](../README.md)开始。

## 按问题阅读

| 你想知道什么 | 阅读入口 |
| --- | --- |
| 能做什么，与 Spectre 对齐到什么程度？ | [能力概览](CAPABILITIES.md) |
| 当前版本包含哪些改动？ | [版本记录](UPDATE.md#baseline-20261009) |
| 如何安装、设置观测或读取结果？ | 下方[接口参考](#接口参考) |
| 电压、积分和事件怎样计算？ | [数学原理](math/README.md) |
| 某项结论依据哪次实际实验？ | [证据索引](development/capability-evidence.md) |
| 如何修改 EVAS、选择测试？ | [开发流程](development/PROCESS.md) |

## 接口参考

| 操作 | 文档 |
| --- | --- |
| 安装 Python 包和 Rust 内核 | [安装](reference/install.md) |
| 核对正在运行的包与内核 | [身份查询](reference/identity.md) |
| 检查 VA 源码能否编译 | [编译准入](reference/frontend-admission.md) |
| 指定实际求解时刻 | [strobe 控制](reference/strobe.md) |
| 保存 JSON、CSV 与运行状态 | [结果导出](reference/results.md) |
| 读取误差区间和采样来源 | [观察证据字段](reference/observation-evidence.md) |
| 解释失败、查询模型和运行记录 | [诊断与只读查询](reference/diagnostics.md) |

## 目录职责

```text
docs/
├── README.md          阅读入口
├── CAPABILITIES.md    面向使用者的能力与结论
├── UPDATE.md          版本变化与历史执行身份
├── reference/         输入、控制与输出接口
├── math/              数学方法、假设与组合边界
└── development/       开发规则、架构和证据维护
```

开发维护材料按需查阅：[架构决策](development/DECISIONS.md)、
[四后端比较规则](development/COMPARISON.md)、[测试追溯矩阵](development/TRACEABILITY.md)、
[诊断来源登记](development/diagnostic-sources.md)。
自动生成的追溯矩阵和诊断机器清单不作为入门阅读材料。

<a id="feature-documentation-contract"></a>

## 文档维护约定

- 能力概览只写当前结论和关键限制，每行保持简短。算法、测试列表和 PR 过程放到对应文档。
- `reference/` 维护接口；`math/` 维护行为、假设、数学方法、状态与误差、代码入口和拒绝边界。
- `development/capability-evidence.md` 维护稳定能力 ID 与证据链接，供追溯工具读取。
- 新能力同步更新契约、能力概览和证据索引。完整实验保留在 `experiments/`，临时推进记录放在 Issue/PR。
- 旧实验保留原执行身份。实现、有限验证和完整 Spectre 兼容性分别说明。
