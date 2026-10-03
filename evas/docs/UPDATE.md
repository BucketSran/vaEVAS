# 更新记录

按版本/检查点倒序记录"改了什么、为什么"。执行身份、收据与逐项证据
不在此重复——见 [CAPABILITIES 检查点身份](CAPABILITIES.md#检查点身份)与
[追溯矩阵](TRACEABILITY.md)。单 PR 的细节以 PR/commit 描述为准，本页只留摘要。

## EVAS 0.12.3 / IR16

- 仿射求解在原关系残差超差时，最多复用 LU 做两次迭代精化；仍按原容差验收。
- 受限方阵在普通 Newton 失败后，可用有次数上限的残差连续化寻找初猜。
  最终解仍须通过原方程、原容差与适用的瞬态认证，不增加未认证输出模式。
- 静态批量支持显式选择 1–64 个线程，保持样本顺序和首个错误下标。
  新增可缩放随机矩阵、批量并行及五类瞬态路径基准。数学与边界见
  [数值手册](math/solving.md)。

## Python 前端与验证护栏（PR48、PR49）

- 前端分离实例编译，补齐参数、算子、输入/响应校验和编译资源上限；超时会回收子进程。
- 增加精确有理数区间性质测试、解析根的随机线性系统、两个有界 fuzz 入口，
  以及有独立答案的 ngspice 子集对照。这些不是原 31 条件的新增资格证据。
- 记录现有积分误差链与电压域架构决策；不引入电流/KCL 或更改 IR16。

## PR35：docs/traceability 重构

- docs/ 重组为 README / UPDATE / PROCESS / CAPABILITIES / math/（四章节迁入）；
  CAPABILITIES 保留支持边界与证据入口，TRACEABILITY 汇集文件级关联。
- 测试文件声明 GUARDS；scripts/traceability.py 校验标签、目标及生成物是否同步，
  不把标签完整当作语义覆盖完整或执行证明。
- 目录迁移后的冻结清单与历史收据恢复原身份；当前导航与固定历史链接分别维护。
- 此前文档重构（examples 三课、validation/smoke 分层、experiments 三分类、
  benchmark/reference 迁入）见对应提交 7d0398d / 6d806a0 / 8de77e9。

## EVAS 0.12.2 / IR16（PR33）

已知事件截止点：共同闭包与截止点各自重跑原 31 条件两档 31/31。
数学细节见 [math/continuous.md](math/continuous.md#known-event-horizons)。

## 更早检查点

PR26–PR32（IR11→IR16 演进）摘要见 [CAPABILITIES 检查点身份](CAPABILITIES.md#检查点身份)；
完整过程叙述保留在各 PR 与固定历史提交，不在本页展开。
