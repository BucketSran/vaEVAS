# 纯 real 函数有限分支对照

两个开发用例检查限幅、实例参数隔离，以及条件捕获发生在局部变量改写之前。
[独立输入与答案](../../../evas/validation/cases/function_branches/)属于 EVAS 验证目录；
[精简对照](comparison.json)保存实际查询样本、源码/工具/检查器身份和失败记录。

| 用例 | 有限观测 | Spectre 与独立答案最大误差 | EVAS 与 Spectre 最大差值 |
| --- | --- | --- | --- |
| dc-table | 5 个实例，3 个时刻，30 个电压值 | `2.7755575615628914e-17 V` | `0 V` |
| continuous-pwl | 2 个实例，8 个时刻，32 个电压值 | `0 V` | `0 V` |

固定绝对判据是 `1e-8 V`。每个查询点在 Spectre 原始 PSF 中恰有一个实际样本，
没有跨限幅拐点插值。EVAS 在同样的查询网格分别执行真实 CLI 和 Rust 内核。
这些是两个已使用的开发用例，不能折算为无条件函数支持或连续全时域验证，
也不表明完整 PA 模型已经可运行。

EVAS 来源为 `44089f7fad5b692906f668dcf3b770900ed64b45`，内核 SHA、IR17 和未知的
嵌入构建修订见 JSON。Spectre 是 `21.1.0.509.isr12 64bit`。
请求全局 `reltol=1e-6`、`vabstol=1e-9 V`；实际瞬态日志显示 conservative 将
瞬态 `reltol` 设为 `1e-7`，`abstol(V)=1e-9 V`、`gear2only`，最大步长分别为
`0.125 s` 和 `0.03125 s`。CPU0 亲和性在日志中可见，命令请求 `+mt=1`，
有效线程数没有独立读回。两例均在单命令 90 秒、license 30 秒、4 GiB 地址空间和
32 MiB 单文件上限下完成，没有超时。

原始冻结模型里的 `vdd=.9`、`if(t>.5)` 使两次 Spectre 编译均以 `VACOMP-1795`
失败，没有波形。这是模型数字写法错误，不是函数行为差异。修正仅补前导零，
原刺激、参数、独立答案和阈值保持不变；EVAS 编译 IR 除源码位置外完全一致。
修正身份重新执行 EVAS 和 Spectre 各两例后通过。总共实际启动 Spectre 四次，
原两次失败仍保留，没有将其改标为成功或盲目重试。

本仓库保留输入、独立答案、[原始观测检查器](check.py)与精简样本。
完整 EVAS 请求/输出、Spectre 原始 PSF、日志与远端逐文件清单是 local-only，
保存在所属工作树的 `runs/function-branches/night-20261007/`；JSON 给出已核验的归档哈希，
没有公共下载地址，因此这份摘要不构成原始数据的公开可复现声明。
原失败输入和修正后的新身份分别保留。远端完成后未观察到所属存活进程，执行通道已释放。

有原始归档时，从仓库根目录执行：

```sh
python3 -B experiments/backends/function-branches/check.py /path/to/spectre-raw-normalized
PYTHONPATH=evas/src python3 -m evas transient evas/validation/cases/function_branches/dc-table.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m evas transient evas/validation/cases/function_branches/continuous-pwl.json --kernel evas/rust_core/target/debug/evas-kernel
```

检查器自带独立接受/拒绝校准，要求原始查询覆盖、唯一信号、有限数值和完整 PSF；
错值、缺查询、重复查询/信号及截断会拒绝。Spectre 使用同目录对应 `.scs`，
源码与期望值均保持固定身份。当前证据属于未合并分支，发布与合并状态由 PR 管理。
