# 原 31 条件：analog 候选与新 Spectre 对照

Spectre21.1.0.509.isr12 新执行62配置；analog运行时9c5d6c5的62配置复用最近验收记录。
main列复用PR26运行时edb004d的历史记录，其源码与当前main的关系见原收据。
P表示原有限观测判据内；正式资格仍I。基础/细化均保留31分母。

| 条件 | main 基础/细化（复用） | analog 基础 | analog 细化 | Spectre 基础 | Spectre 细化 |
| --- | --- | --- | --- | --- | --- |
| v1-main | 编译拒绝 / 编译拒绝 | P | P | P | P |
| v2-main | P / P | P | P | P | P |
| v2-reference-zero | P / P | P | P | P | P |
| v2-supply-fixed | P / P | P | P | P | P |
| v2-input-common-mode | P / P | P | P | P | P |
| v3-main | P / P | P | P | P | P |
| v4-c0 | P / P | P | P | P | P |
| v4-c1 | P / P | P | P | P | P |
| v5-main | P / P | P | P | P | P |
| v6-standard | 编译拒绝 / 编译拒绝 | 编译拒绝 | 编译拒绝 | P | P |
| v7-linear-main | P / P | P | P | P | P |
| v7-linear-swapped | P / P | P | P | P | P |
| v7-linear-a-half | P / P | P | P | P | P |
| v7-nonlinear-0.5 | 内核拒绝 / 内核拒绝 | 内核拒绝 | 内核拒绝 | P | P |
| v7-nonlinear-2.0 | 内核拒绝 / 内核拒绝 | 内核拒绝 | 内核拒绝 | P | P |
| e1-aligned | P / P | P | P | P | P |
| e1-shifted | P / P | P | P | P | P |
| e1-slow | P / P | P | P | P | P |
| e2-low | P / P | P | P | P | P |
| e2-clock-high | P / P | P | P | P | P |
| e2-reset-high | P / P | P | P | P | P |
| c1-main | P / P | P | P | P | P |
| c1-swapped | P / P | P | P | P | P |
| c1-no-reset-a | P / P | P | P | P | P |
| c2-main | 编译拒绝 / 编译拒绝 | 编译拒绝 | 编译拒绝 | P | P |
| d1-free | P / P | P | P | P | P |
| d1-reset | P / P | P | P | P | P |
| d2-constant | 编译拒绝 / 编译拒绝 | 编译拒绝 | 编译拒绝 | P | P |
| d2-chirp | 编译拒绝 / 编译拒绝 | 编译拒绝 | 编译拒绝 | P | P |
| s1-default | P / P | P | P | P | P |
| s1-override | P / P | P | P | P | P |

main24/31；analog25/31；Spectre31/31（每档）。
对应的旧候选分支对剩余6条各自新执行两档，三分支均4/4，尚未统一基线及IR。

[完整收据](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/pr14-pr15-validation/results/analog-gap-spectre-comparison.json)；[解释与边界](../RESULTS.md#analog-gap-spectre-comparison)。
