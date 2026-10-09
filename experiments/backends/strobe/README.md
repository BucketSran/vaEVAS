# Strobe 的有限实际对照

本轮增加独立强制求解点后，用四个冻结模型与实际 Spectre 配对。
模型、刺激和预算在运行前固定，见 [验证夹具](../../../evas/validation/strobe/README.md)。
当前实现范围见 [控制契约](../../../evas/docs/reference/strobe.md)。

Spectre 版本为 `21.1.0.509.isr12`，新执行恰好4次模拟和1次版本查询，无重试。
输入 deck 请求 `reltol=1e-7`、`vabstol=1e-9 V`、`iabstol=1e-12 A`、
`maxstep=0.5 s`、`errpreset=conservative` 和 `strobeoutput=all`。
原生日志实际打印 `reltol=1e-8`、`method=gear2only`。该差异保留，不能称为两端相同数值设置。
旧通用读回工具还缺少准备元数据，其原 I 结果没有被手工摘录改写为 P。

EVAS 最终运行源码为 `940e5600f60299d52a7e23ea1562232accdd37c7`，
内核来自独立 Cargo 构建，完整身份、输入、响应及分析脚本 SHA256 在 [配对收据](pairing.json)。
它重用本轮原始 Spectre 波形，没有重复启动 Spectre。上一候选 `5911c89e` 的配对保留在本地。
本轮只修正强制点查找对正负零的处理，没有改动这些四例的非零时间表或数值方程。

| 模型 | 内部强制点 | 已存在共同点的最大电压差 | 原生时间覆盖 |
| --- | --- | --- | --- |
| 静态线性、不规则表 | 2 | 0 V | t=0 缺失，I |
| 连续反馈、周期表 | 4 | 4.35e-8 V | 全部请求点存在 |
| 隐式动态、不规则表 | 2 | 4.74e-12 V | t=0 缺失，I |
| timer 计数、周期表 | 4 | 0 V | 全部请求点存在；stop=1 单列，计数4 |

12个内部强制点全部满足冻结的 `1e-6 V` 直接比较预算。
表中最大值也包含已经存在的端点，连续反馈内部点最大差为 `4.10e-8 V`。
缺失观测不通过插值或最近点填补；参考完整覆盖和设置资格没有统一升级为 P。
PSF十进制导出的精确数值命中也不证明隐藏回调的物理次序。
原 C1、#79、VCO 的严格 F/I、原模型和预算继续保留。

[原生设置摘录](native-settings.json)保存原日志哈希及打印行。
[执行计划身份](reference-identity.json)保存冻结计划、工具和收集清单哈希；原生波形哈希在配对收据每例的 `native_psf_sha256`。
这些精简记录是 repository-contained；全部 raw 波形、完整日志、运行 bundle、
审查报告及唯一决策 TSV 为 local-only，保存在可见集成工作区的
`runs/alignment-implementation-20261009/strobe/` 与上级 `decisions.tsv`。
文件哈希不是公开下载地址，不宣称完整原始数据已公开复现。

具备该本地参考目录时，可以新建输出目录重跑：

```sh
PYTHONPATH=evas/src python3 experiments/backends/strobe/pair.py \
  --reference runs/alignment-implementation-20261009/strobe/reference \
  --out runs/strobe-new-pairing --kernel evas/rust_core/target/debug/evas-kernel
```

脚本保存新执行身份、验证完整 bundle 哈希、核对冻结分母和独立解析公式，
并对每个精确时间的全部原生行计算值差。它不生成参考波形，不替代参考精度资格流程。

<a id="scs-adapter-checkpoint"></a>

## 2026-10-09 SCS 接入与开发基线

PR #118 收窄为将已有五项强制点控制接入 `.scs`。Rust 求解器文件树与已合入的
`c2ca32ee` 完全相同，原 [f3618c49 的源驱动局部历史候选](https://github.com/BucketSran/vaEVAS/tree/f3618c4930b360651080e7e5d2dbdaa2c97abe7c/experiments/backends/source-event-closure)
未纳入本次基线；其四份完整直接比较 F 和全部原始证据保留，由 #96 继续跟踪。

本次重建内核后，新执行四个相同模型的 `.scs` 请求，复用上文四份实际 Spectre 波形。
SCS 接入与公共控制共18项测试通过。12个内部强制点满足原1 µV直接预算，
最大差为连续反馈的约41.0 nV；独立公式也通过。原两处 t=0 缺失及有效设置资格 I 保留。
为适配电压域入口，本地网表显式移除 `iabstol`、`precision`、`errpreset` 和 `strobeoutput`；
模型、刺激、初态与强制时刻不变，不声称后端内部设置相同。

[接入收据](scs-adapter.json)绑定源文件、Rust文件树、内核、请求和结果身份。
维护的 `pair.py` 另验证已有参考 bundle 的身份并复验 API 路径；原参考未重跑。
同一内核对 Spec B 原12请求的响应逐字节保持，仅支持当前版本保持性，不改其原严格 F/I。
新完整请求/响应、网表、复验脚本和检查日志为 local-only，保留在可见工作区的
`runs/baseline-consolidation-20261009/`。本次没有新增远端 Spectre 调用。
