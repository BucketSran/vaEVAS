# TDD 开发流程

本页是**规则**（怎么走流程）；实际记录不在此维护——
每个条件的"契约 → 测试 → 实现 → 收据"四联由
[追溯矩阵](TRACEABILITY.md)自动汇集，版本级摘要见 [UPDATE.md](UPDATE.md)。

## 证据分层

| 层 | 位置 | 回答 | 资格 |
| --- | --- | --- | --- |
| 演示 | `evas/examples/` | va/json 怎么写 | 教学，无证据资格 |
| 冒烟 | `evas/validation/smoke/` | 链路通不通 | 连通性，无语义资格 |
| 回归护栏 | `evas/tests/` | 这次改动有没有破坏已知行为 | 开发资产 |
| 判据 | `evas/validation/` | 正确答案是什么、怎么判定 | 可对外引用 |
| 执行证据 | `experiments/` | 某版本实际跑出什么 | 可对外引用（收据） |

## 新能力 / 语义变更的五步流程

```
1. 契约    在 validation/ 写契约：条件 ID、模型、独立数学答案、阈值、拒绝条件
2. 测试    在 tests/ 写回归：文件顶部 GUARDS = ["<条件ID或能力ID>"]，
           期望值必须独立推导（分数/闭式/Decimal），不得以实现输出为 oracle；
           实现存在前测试应为红（TDD），补齐型回归须在 docstring 声明补齐性质
3. 实现    Python 前端 + Rust 内核；不支持的语义给显式诊断，不静默回退
4. 矩阵    跑 validation 正式矩阵，收据登记进 experiments/（绑定源码/内核身份）
5. 文档    math/ 对应章节按特性文档契约更新；CAPABILITIES 行更新范围/缺口；
           追溯矩阵重新生成
```

## 硬性检查（可机械执行）

- 新测试文件必须声明 `GUARDS`；纯开发回归用 `GUARDS = ["DEV:<主题>"]` 诚实标注。
  `scripts/traceability.py --check` 会拒绝无标签文件。
- 期望值独立性写进测试 docstring（来源：手算/精确有理数/闭式解/Decimal）。
- 契约没有独立答案的，不得声称通过测试即验证。
- 正式验证资格只来自 validation 矩阵执行；tests 全绿 ≠ 验证资格。

## 追溯矩阵

由 `scripts/traceability.py` 扫描测试 `GUARDS` 标签与 validation 契约生成
[TRACEABILITY.md](TRACEABILITY.md)。矩阵是**生成物**：修改测试标签或契约后
重新运行脚本，不手编矩阵文件。缺口（无测试守护的条件、无契约对应的测试）
由脚本一并报告，作为补测试 roadmap 的输入。
