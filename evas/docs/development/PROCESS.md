# TDD 开发流程

本页说明 EVAS 行为变更的开发顺序，检查范围按
[验证规则](../../../.agents/skills/evas-validate/SKILL.md#select-the-necessary-checks)选择。
[追溯矩阵](TRACEABILITY.md)提供文件级导航；实际执行与红/绿结果记录在对应 PR，
数学章节提供实现入口，收据保留被测版本与原始结果。

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
2. 测试    在 tests/ 写回归：文件顶部 GUARDS = ["<契约ID或能力ID>"]，
           期望值必须独立推导（分数/闭式/Decimal），不得以实现输出为 oracle；
           实现存在前测试应为红（TDD），补齐型回归须在 docstring 声明补齐性质
3. 实现    Python 前端 + Rust 内核；不支持的语义给显式诊断，不静默回退
4. 验证    按改动与组合风险选择检查；影响原矩阵结论时重跑受影响配置并留新收据
5. 文档    math/ 对应章节按特性文档契约更新；CAPABILITIES 概览更新结论与关键限制；证据索引更新来源；
           追溯矩阵重新生成
```

文档和标签修改通常只需一致性检查；不要求全矩阵或远端仿真。
先红后绿描述新增行为测试的实践，生成的矩阵不能证明这个时间顺序。

## 标签与机械检查

- 测试文件声明一个非空字符串列表 `GUARDS`。能力 ID 取自 [能力 ID 与证据索引](capability-evidence.md)，
  契约 ID 取自生成器登记表。直接使用某个验证模型时加 `case:<cases子目录名>`；
  模型可以对应多个运行条件，模型标签不代表这些条件已被执行。
- 开发主题可用 `DEV:<小写主题>`，例如 `DEV:ir-migration`，可与契约标签并存。
- `scripts/traceability.py --check` 拒绝缺失、重复、空或未知标签、失效本地目标，
  以及未更新的矩阵。它不导入或执行测试；关联是否准确仍需读代码审查。

## 独立答案与资格

- 期望值独立性写进测试 docstring（来源：手算/精确有理数/闭式解/Decimal）。
- 契约没有独立答案的，不得声称通过测试即验证。
- 正式验证资格还要求满足验证协议的完整条件；矩阵执行或 tests 全绿都不能单独给出资格。
  当前原矩阵已用于开发，资格限制见 [METHOD_QUALIFICATION](../../validation/METHOD_QUALIFICATION.md)。

## 追溯矩阵

脚本读取测试标签、能力 ID 与证据索引、已登记契约和 DUT 目录，生成
[TRACEABILITY.md](TRACEABILITY.md)。新增契约须先登记；脚本不解析契约自然语言，
不枚举所有语义组合，也不自动连接逐个测试方法与运行收据。
修改这些输入后，从仓库根目录执行：

```sh
python3 -B scripts/traceability.py
python3 -B scripts/traceability.py --check
```

无关联只表示没有对应的标签声明，不能直接解释为能力缺失或未验证。
历史收据、冻结清单和固定提交链接不随当前目录改写；新位置在当前索引维护。
