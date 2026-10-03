# 历史原 31 条件：缺口补齐检查点（2026-10-01）

EVAS 运行时 `39a4545c34fb22b1bd69731ca6b8bd8852b0e9dd`，IR v15；执行时为本地候选。
该实现后随 PR29 合并；当前范围与证据从[能力表](../../../../evas/docs/CAPABILITIES.md)进入，不改写下表原结果。
“达”仅指原检查器的 `observations_within_targets`，正式资格仍 I。两档分别以 31 为分母。
EVAS 为本轮 62 次新执行；Spectre 为上一轮 62 次执行的导出结果重新核验，未新启动远端任务。
相对 analog 候选 `9c5d6c5`，新增六条条件、12 个配置；原达标 50 份 CSV 逐字节一致。
完整输入、设置、检查器和输出身份见[收据](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/results/gap-completion-current.json)，数学及范围见[复审入口](../REVIEW.md#gap-completion)。

| 原条件 | EVAS 基础 | EVAS 细化 | Spectre 基础（复用重判） | Spectre 细化（复用重判） | 相对 analog 基线 |
| --- | --- | --- | --- | --- | --- |
| `v1-main` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v2-main` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v2-reference-zero` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v2-supply-fixed` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v2-input-common-mode` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v3-main` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v4-c0` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v4-c1` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v5-main` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v6-standard` | 达 | 达 | 达 | 达 | 新增达标 |
| `v7-linear-main` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v7-linear-swapped` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v7-linear-a-half` | 达 | 达 | 达 | 达 | CSV 不变 |
| `v7-nonlinear-0.5` | 达 | 达 | 达 | 达 | 新增达标 |
| `v7-nonlinear-2.0` | 达 | 达 | 达 | 达 | 新增达标 |
| `e1-aligned` | 达 | 达 | 达 | 达 | CSV 不变 |
| `e1-shifted` | 达 | 达 | 达 | 达 | CSV 不变 |
| `e1-slow` | 达 | 达 | 达 | 达 | CSV 不变 |
| `e2-low` | 达 | 达 | 达 | 达 | CSV 不变 |
| `e2-clock-high` | 达 | 达 | 达 | 达 | CSV 不变 |
| `e2-reset-high` | 达 | 达 | 达 | 达 | CSV 不变 |
| `c1-main` | 达 | 达 | 达 | 达 | CSV 不变 |
| `c1-swapped` | 达 | 达 | 达 | 达 | CSV 不变 |
| `c1-no-reset-a` | 达 | 达 | 达 | 达 | CSV 不变 |
| `c2-main` | 达 | 达 | 达 | 达 | 新增达标 |
| `d1-free` | 达 | 达 | 达 | 达 | CSV 不变 |
| `d1-reset` | 达 | 达 | 达 | 达 | CSV 不变 |
| `d2-constant` | 达 | 达 | 达 | 达 | 新增达标 |
| `d2-chirp` | 达 | 达 | 达 | 达 | 新增达标 |
| `s1-default` | 达 | 达 | 达 | 达 | CSV 不变 |
| `s1-override` | 达 | 达 | 达 | 达 | CSV 不变 |

未更改原 DUT、刺激、两档目标或独立检查器，也未删除拒绝记录来改变分母。
这 31 条件已用于开发，不是未见确认集；本表不证明全时域最大误差、完整 VA 合规或速度优势。
