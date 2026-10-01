# EVAS IR15 联合交付与验证

本检查点整合普通 analog 局部赋值/输入条件、一阶滤波、相位和无状态多项式瞬态，
保留已交付的事件与积分复位能力。数学、试算生命周期和拒绝范围分别由
[能力表](../../evas/docs/CAPABILITIES.md)、[手册](../../evas/docs/README.md)与[复审记录](REVIEW.md)维护。
运行时固定于 `d451605bf9991ceea010c68af9cb1143f1b50754`，EVAS 0.9.0 / IR v15；没有发布 tag。

## 当前证据

| 收据 | 实际执行与限制 |
| --- | --- |
| [精度链检查](results/precision-chain-checks.json) | 372 Python、83 Rust、locked build、Clippy、格式与冻结身份检查通过；一项旧性能探针 ignored；保留旧内核 RED 和修复过程失败 |
| [原 31×2 矩阵](results/precision-chain-matrix.json) | 62 次新本地执行，两档各 31/31；CSV、判定与生效设置和 ddfd379 一致；输入、阈值、检查器与分母未改 |
| [数学/兼容 review](REVIEW.md#precision-chain) | 点输入根误差证明，无条件 PWL/采样状态误差传播，实际接受帧的失败回退；无法证明预算时拒绝 |

矩阵 JSON 保留全部原字段和逐配置值，格式改为每条记录一行；检查收据同时记录原格式与当前格式
SHA256。这是排版整理，不是新执行或重判。最新修复没有新 Spectre 执行或性能测量。

执行内核 SHA256：`0d92e770471638182f05fec53c308c0b34d89935c25bbaf70d47f5c9c33f522f`。
原始波形、日志、两版内核、输入与源码快照在 ignored 的
`runs/precision-chain-20260930T202707Z-e1c89a/`，为 **仅本地保留**。
RAW_MANIFEST SHA256：`a55ea465456f812f05f06be6673e4b9dbc323f38b89ed0f349319521b0a727af`，
绑定 876 文件、172,681,211 字节；此归档没有因交付整理而改写。
正式 DVS 资格仍 **I**；原条件已参与开发，有限观测满分不是全时域精度或未见确认集。

## 复现入口

普通使用与开发回归见[构建/API](../../evas/README.md#构建与运行)。
重跑原矩阵需要记录中指明的冻结输入归档（仅本地保留）；分析程序验证输入、执行源码、内核、
波形和清单，再调用未修改的[原独立检查器](../dvs2-spectre-validation/check_results.py)。
以下命令在仓库根目录运行，输出使用新目录；占位路径须替换为实际输入和身份：

```sh
python3 -B experiments/pr14-pr15-validation/matrix.py evas \
  --source runs/FROZEN-INPUTS --root runs/NEW-MATRIX \
  --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/parallel-gap-integration/analyze.py \
  --source runs/FROZEN-INPUTS --run runs/NEW-MATRIX \
  --identity runs/NEW-SOURCE-IDENTITY.json --output runs/NEW-ANALYSIS.json
```

`NEW-SOURCE-IDENTITY.json` 必须绑定实际源码与构建身份；格式见当前矩阵的 `execution_identity`，
不能复制旧身份描述新内核。上述是复现入口，不声明外部读者已能取得完整 frozen/raw。
兼容比较可对 gzip 归档解压出的原 JSON 使用 `--baseline`；历史 Spectre 重判用
`--spectre-receipt`，不计为新 Spectre 仿真。

## 历史与资产

重复的长篇历史叙述保留在[固定交付前快照](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/REVIEW.md)。
六份大历史 JSON 以 `.json.gz` 在仓库内无损保存；
[归档清单](results/historical-receipts.json)记录原路径/字节数/SHA256、压缩文件身份与固定历史链接。
只有整理收据被压缩，完整 raw 波形/日志仍为仅本地保留。

| 固定检查点 | 历史入口 |
| --- | --- |
| 初期 IR14 与已发现反例 | [协议快照](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/parallel-gap-integration/README.md)、[矩阵摘要](results/MATRIX.md)、[原收据 gzip](results/original31.json.gz) |
| 联合功能 `39a4545` | [数学/范围](REVIEW.md#gap-completion)、[31 行摘要](results/gap-completion-matrix.md)、[矩阵 gzip](results/gap-completion-current.json.gz)、[检查 gzip](results/gap-completion-checks.json.gz) |
| 查询/根认证优化 `ddfd379` | [原理/测量](REVIEW.md#accuracy-optimization)、[矩阵 gzip](results/accuracy-optimization-matrix.json.gz)、[计时收据](results/accuracy-optimization-profile.json) |
| analog 单项与 Spectre 原执行 | [历史结果](../pr14-pr15-validation/RESULTS.md#analog-gap-spectre-comparison)、[Spectre 收据 gzip](../pr14-pr15-validation/results/analog-gap-spectre-comparison.json.gz)、[analog 收据 gzip](../pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz) |

例如无损解压至 ignored 输出目录后，原有 JSON 分析器可读取；清单中的 `original_sha256`
针对解压后的字节，不是压缩文件：

```sh
mkdir -p runs/RECEIPT-RESTORE
gzip -dc experiments/parallel-gap-integration/results/accuracy-optimization-matrix.json.gz > runs/RECEIPT-RESTORE/accuracy-optimization-matrix.json
```

合并保留这些历史提交及失败身份。历史记录中的“本地候选/未合并”描述的是当时的执行状态，
不代表当前交付状态；旧成绩也不改写为新源码的实验。
