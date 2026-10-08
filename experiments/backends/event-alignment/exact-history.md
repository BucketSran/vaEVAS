# 常数积分历史的精确查询阶段

此增量修复 Spec B 原 E3/E5 完整请求的阶段拒绝，不解决 C1 callback、VCO 原环回左邻点或 va07 原 stop=3 计数差。PR #108 继续 draft，未授权兼容例外。

生产提交为 `4ae69045567dd6eda7460536ba6e72d122ec9964`；正常合入 main `d1dde9c931a5c6bf814911df9adec2645576fc15` 后为 `b857c4e0`，该整合没有修改 Rust。具体请求、响应及核身份见 [实际收据](evidence/exact-affine-history.json)。[修复前收据](evidence/pre-exact-history-integration.json) 保留原 8P/4 拒绝，不能当作最新结果。

## 问题和修复

原 E3 的数学历史为 `.25` 前斜率 1、之后斜率 2，guard 根恰在 `.5`。原 E5 的 guard 根为有理数 `1/3`，binary64 `float(1/3)` 在根前。旧 #103 请求曾接受两者，但 E3 在 `.5` 给前态；之后的物理阶段检查拒绝不能证明的根盒内查询。因此不能简单恢复旧分支。

新证明仅覆盖无 reset、反馈、源驱动或滤波器的自主常数 `idt` 线性历史。精确 IC、常数导数和输出映射都必须有单点来源；单点事件重启从旧证明精确推进，非点窗口保持原区间种子并丢弃精确来源。算术复用原精确源预算。guard 的有理数根须包含在原隔离盒中；保留原 discovery 盒与根归属，观察盒只与严格外包络相交，继续走原容差、stop 和因果检查。查询按真实有理根排序；相同浮点包络中的两个不同根不能合并。采样、history seed 和排序消费者共用精化后的观察盒，不能从中心值重建来源。

独立 Astra 源审与重放报告保存在当前任务的 `runs/issue-closure-20261008/review/exact-affine-history-astra.md`。其原则判断是沿用已有 PWL `RootTime` 的证书精化。最终审查身份由父任务固定发布，不能把先前 resource/closure 审查算作这个新增源码已经受审。

## 实际验证

原十二个 E1–E6 base/fine 请求最新执行均 numeric/event P；原科学设置、查询列表不变，Program 只由 schema 17 更新为 18。每次配对前校验实际返回 times、nodes、形状及有限值。原 checker 的事件窗口保持不变；这些 P 不构成一般严格 callback 资格。

新增独立回归验证 E3 `.5` 后态、E5 `float(1/3)` 前态及邻接查询的阶段，完整/邻接/稀疏网格事件记录相同。负控覆盖盒外伪证书、同浮点包络不同根、不够大的原 ttol、未知非点种子、reset/反馈、一般多项式 guard 及同 controller 失败后回退重试。实际组合 Python 86P，完整 Rust 210P/1 ignored；之后增加的 reset/反馈单测另跑 1P，精化与历史重试负控另跑。整合 main 后默认 fall、local-state 与 case 30P；最终六个 mixed 网格重放保持原有限 P/覆盖 I。各项身份见收据，未把旧 #103 十二响应身份当作本次执行。

实际 Spectre 复用原同模型 archive `859b4c010f595e82c1f83d8358525aade733bcf563b5c3999d17fed80b05c7d7`，共享 archive 校验器核对 415 个正规成员。E3 两 profile 各有两个原生时刻的计数为 Spectre 1 / EVAS 0，严格阶段 F 保留；连续电压最大差约 10 nV。E5 配对计数相同，连续最大差约 2 nV。四配置各有一个原始末行 `2.0000000000000013` 超过原 stop=2，保留该行并标完整原生配对覆盖 I，没有延长 stop。精确 callback 来源资格仍 I；新精确 callback 探针是单独证据，不能由 PSF token 推定。

## 公开重放

在仓库根目录构建匹配内核后运行：

```sh
PYTHONPATH=.:evas/src python3 -B experiments/backends/event-alignment/exact-history/replay.py \
  --kernel evas/rust_core/target/debug/evas-kernel \
  --output runs/exact-history-replay
```

入口使用公开的十二个 manifest，逐项保存完整实际请求与响应、校验返回协议并运行原 checker。有原始 #103 请求目录时可加 `--historical-requests PATH`，严格比较 Program 除 schema 外的字段及全部其他请求字段。其结果只能说明本地请求通过；严格 Spectre 差异与覆盖缺口仍单列。
