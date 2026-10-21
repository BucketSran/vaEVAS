# #138 候选扩展提案（草稿，未发 issue）

日期：2026-10-17。合成来源：
- 内部热点分析 `2026-10-17-evas-acceleration-analysis.md`（main `e2c7aac7` 实测：nonlinear_idt 222ms 主导；trial 全量 clone、事件全量重建、非线性区间 Jacobian 每步重算）
- 外部调研 `2026-10-17-external-acceleration-survey.md`（Spectre-X/PrimeSim/Xyce/KLU/batched BLAS 做法 + 仿射算术等数学方向）

## 建议新增候选（编号接 P16 之后）

| ID | 候选 | 风险 | 外部先例/数学依据 | 对应模块 | 启动条件 |
| --- | --- | --- | --- | --- | --- |
| E1 | 仿射算术（affine arithmetic）认证外包络 | B | 相关误差不膨胀→更少分裂/缩步；包含性不弱于区间法 | `implicit_dynamics.rs` 认证路径 | P03 切片结论出来后 |
| E2 | 符号结构复用扩展到非线性区间 Jacobian | A 子集 | KLU 符号复用、ngspice 稀疏 LU 先例；保持消元序→逐字节验收 | `nonlinear.rs` | **已在实施**（codex/p03-nonlinear-jacobian-reuse） |
| E3 | cheap enclosure 粗筛 + 原认证兜底 | B（组织近 A） | Lohner/Corliss 两层筛标准结构；EVAS 均值定理路径已是雏形 | `settlement_bounds.rs` | 先只读量化粗筛命中率 |
| E4 | 事件定位的 guard 导数复用 | B | 定位迭代次数↓；复用已有解析导数 | `events.rs` | 需定位迭代计数证据 |
| E5 | 批量小矩阵 SIMD 核（VILIB 式区间向量化） | B | Goualard/VILIB 先例 | 数值核 | P03 落地后评估规模 |

暂缓：SMW 秩一更新（适用面窄）、Taylor models（远期）、GPU（P16 条件未满足）。

## 与现有清单的衔接

- E2 即 P03 的具体化，不重复登记，完成后回填 P03 行
- E1/E3 均属 P04 认证加速族，登记后仍须单独验证包含性与拒绝边界（issue 红线）
- 排序依据：nonlinear_idt 是实测主热点，E2 直接命中；E1/E3 攻击缩步/分裂的根因（区间保守性）

## 验收（全部沿用 #138 原规则）

A 类逐字节一致；B 类区间包含性（精确有理数/高精度独立答案、覆盖应拒绝案例）；交替五轮计时报中位数/范围；Spectre 对照按项目规则复用冻结参考。
