# EVAS 联合验证与演进

本目录检查新能力组合后，电压方程、事件、算子历史和误差预算能否继续一致。
它保存原 31 条件回放、精度链、连续动态及共同生命周期的结果，也保留开发中的反例与失败。
数学和支持边界分别由[技术手册](../../../evas/docs/README.md)及[能力表](../../../evas/docs/CAPABILITIES.md)维护。

当前 EVAS 0.12.2 / IR16 由 [PR33](https://github.com/BucketSran/vaEVAS/pull/33)
合并到 main `b4921ca`，尚未发布版本 tag。
README 给出当前证据和使用入口；各阶段完整记录见[固定历史报告](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md)，
数学与兼容性审查在 [REVIEW](REVIEW.md)。

## 当前证据

运行时 `8618339` 和审查头 `18063c9` 已由 PR33 合并。以下是已执行并绑定该源码的证据，
本次文档整理没有新执行；数学与支持边界见[事件截止点](../../../evas/docs/math/continuous.md#known-event-horizons)。

| 收据 | 实际执行与限制 |
| --- | --- |
| [截止点开发检查及合并前审查](results/event-horizon-checks.json) | 506 Python、124 Rust 通过，1 个旧性能探针 ignored；locked build、Clippy、格式通过。9 个新增 Python 方法、2 个 Rust 私有测试及 3 组解析审查探针不增加原矩阵分母 |
| 同收据的原 31×2 矩阵 | 两档各 31/31；62 份 CSV 与 PR32 基线逐字节一致，输入、检查器和数值设置不变，仅引擎版本元数据更新 |
| [前一共同闭包的观察/依赖修复](results/lifecycle-observation-review-fixes.json) | PR32 被测运行时 `1b99c33`；与当时源码快照一致，执行时的状态字段保留 |

最终内核 SHA256：`d66cb9b0622b744cc49f38e0fcc23d3f98ffc55c60fbc863a3f2f492beb0205e`。
收据保存执行时快照与后续审查/集成记录；`status` 不是当前 PR 状态。
固定 raw 清单、原始失败和补充探针均为 **仅本地保留**，工作区清理后通过本地归档路径映射取回。
正式 DVS 资格仍 **I**；没有新 Spectre 执行、性能测量或一般连续时间资格声明。

## 按问题回看历史

| 主题 | 实验与审查 |
| --- | --- |
| 历史误差为什么要继续传入输出验收？ | <a id="ir15-precision-chain"></a>[IR15 精度链](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#ir15-precision-chain)、[数学审查](REVIEW.md#precision-chain) |
| 线性动态、积分反馈、高阶滤波与 ddt 如何联合？ | <a id="continuous-dynamics"></a>[IR16 连续动态](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#continuous-dynamics) |
| 一般非线性动态与联合复位怎样补齐？ | <a id="dynamic-closure"></a>[动态补齐](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#dynamic-closure) |
| DAE、混合算子、非精确事件采样如何认证？ | <a id="certified-mixed-dynamics"></a>[混合动态](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#certified-mixed-dynamics) |
| 冷启动、续算、复位观察与 Spectre 有哪些差异？ | <a id="shared-lifecycle-review"></a>[第一批共同生命周期对照](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#shared-lifecycle-review) |
| 怎样把观察、未来安装与原子提交分开？ | <a id="lifecycle-closure-review"></a>[共同闭包实现](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#lifecycle-closure-review) |
| 根时刻误差或导数消元后的瞬时依赖是否会遗漏？ | <a id="lifecycle-observation-review-fixes"></a>[追加修复](https://github.com/BucketSran/vaEVAS/blob/f3440b214e10294de2135415fac4ac72d121d6d6/experiments/runs/parallel-gap-integration/README.md#lifecycle-observation-review-fixes) |

这些记录绑定各次被测源码与构建，保留原始失败和修复过程。
重判历史 Spectre 波形不计为新执行，开发回归不增加原矩阵条件数。

## 复现入口

普通使用与开发回归见[构建/API](../../../evas/README.md#构建与运行)。
重跑原矩阵需要记录中指明的冻结输入归档（仅本地保留）；分析程序验证输入、执行源码、内核、
波形和清单，再调用未修改的[原独立检查器](../../backends/dvs2-spectre-validation/check_results.py)。
以下命令在仓库根目录运行，输出使用新目录；占位路径须替换为实际输入和身份：

```sh
python3 -B experiments/archive/pr14-pr15-validation/matrix.py evas \
  --source runs/FROZEN-INPUTS --root runs/NEW-MATRIX \
  --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/runs/parallel-gap-integration/analyze.py \
  --source runs/FROZEN-INPUTS --run runs/NEW-MATRIX \
  --identity runs/NEW-SOURCE-IDENTITY.json --output runs/NEW-ANALYSIS.json
```

`NEW-SOURCE-IDENTITY.json` 必须绑定实际源码与构建身份；格式见当前矩阵的 `execution_identity`，
不能复制旧身份描述新内核。上述是复现入口，不声明外部读者已能取得完整 frozen/raw。
兼容比较可对 gzip 归档解压出的原 JSON 使用 `--baseline`；历史 Spectre 重判用
`--spectre-receipt`，不计为新 Spectre 仿真。

## 历史与资产

重复的长篇历史叙述保留在[固定交付前快照](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/runs/parallel-gap-integration/REVIEW.md)。
六份大历史 JSON 以 `.json.gz` 在仓库内无损保存；
[归档清单](results/historical-receipts.json)记录原路径/字节数/SHA256、压缩文件身份与固定历史链接。
只有整理收据被压缩，完整 raw 波形/日志仍为仅本地保留。

| 固定检查点 | 历史入口 |
| --- | --- |
| 初期 IR14 与已发现反例 | [协议快照](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/runs/parallel-gap-integration/README.md)、[矩阵摘要](results/MATRIX.md)、[原收据 gzip](results/original31.json.gz) |
| 联合功能 `39a4545` | [数学/范围](REVIEW.md#gap-completion)、[31 行摘要](results/gap-completion-matrix.md)、[矩阵 gzip](results/gap-completion-current.json.gz)、[检查 gzip](results/gap-completion-checks.json.gz) |
| 查询/根认证优化 `ddfd379` | [原理/测量](REVIEW.md#accuracy-optimization)、[矩阵 gzip](results/accuracy-optimization-matrix.json.gz)、[计时收据](results/accuracy-optimization-profile.json) |
| analog 单项与 Spectre 原执行 | [历史结果](../../archive/pr14-pr15-validation/RESULTS.md#analog-gap-spectre-comparison)、[Spectre 收据 gzip](../../archive/pr14-pr15-validation/results/analog-gap-spectre-comparison.json.gz)、[analog 收据 gzip](../../archive/pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz) |

例如无损解压至 ignored 输出目录后，原有 JSON 分析器可读取；清单中的 `original_sha256`
针对解压后的字节，不是压缩文件：

```sh
mkdir -p runs/RECEIPT-RESTORE
gzip -dc experiments/runs/parallel-gap-integration/results/accuracy-optimization-matrix.json.gz > runs/RECEIPT-RESTORE/accuracy-optimization-matrix.json
```

合并保留这些历史提交及失败身份。历史记录中的“本地候选/未合并”描述的是当时的执行状态，
不代表当前交付状态；旧成绩也不改写为新源码的实验。
