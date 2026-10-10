# Strobe 的实际对照

<a id="timer-fix"></a>

## 2026-10-10 固定 timer 与连续历史

**原 12 组定时采样的 strobe 拒绝已修复，沿用原模型、观察点和误差预算，全部通过。**
本次在服务器重新构建 EVAS，并实际执行 50 组 EVAS、34 组 Spectre 配置。
两端使用相同模型和刺激，各自对独立答案验收；共同原生时刻的直接值差另作诊断。
结果不表示每个事件边界逐点相同。支持结论汇总于[主表](../../../evas/docs/COMPARISON.md)，
逐配置身份、误差、有效设置和失败保存在[本次收据](20261010-timer-fix.json)。

本次检查了什么：

- 原定时采样三例 × 四档：EVAS、Spectre 各 12/12 通过。原首轮的 12 次拒绝保留。
  同批阈值采样两端各 4/4 通过；新 EVAS 内核对原四个一阶滤波条件的四档复验为 16/16。
- 定时采样→保持→`transition`→一阶滤波：正常边沿、中断边沿、双实例三例，
  两端各 12/12 通过。保留原 SEF 的 100 µV 输出、10 nV 输入和 ±5 ps 事件预算。
- 定时采样→`idt`：EVAS 四档通过；Spectre 四档相对名义采样的积分误差约 115.49 µV，
  超过预先固定的 100 µV。这四个失败没有被删除或改判。

### 积分差异来自哪里

积分例每 1 µs 更新一次保持值，`timer` 明确允许 100 ps 时间偏移。
实际计数输出显示，Spectre 在名义时刻前约 100 ps 更新；EVAS 在名义事件的可表示上界更新。
因此，两端取到的保持值和每段积分的长度都略有不同。收紧求解容差或减小最大步长，
没有消除原四档的约 115.49 µV 差异。

为检查这一原因，追加两端各两次控制实验：只将模型的 `TT` 参数收紧为 10 ps、1 ps，
保持原源码、输入、观察点、100 µV 数值预算，以及“同时收紧”档的求解设置。
Spectre 的名义积分误差分别降至 **11.61 µV、1.18 µV**；EVAS 均约为 1.60×10⁻¹⁴ V。
这支持“允许的采样时移传到了积分输出”的解释，不是 EVAS 需要复制的积分错误。
这两个补充配置不替换原四个失败，也不代表原 100 ps 条件已经满足名义输出预算。

### 修复和证据边界

原固定时钟的区间乘加多扩张了一层舍入，可能把事件执行点推过请求的 strobe 时刻。
新路径用精确时钟关系确定最窄浮点包围，先真实提交事件及其历史，再接受强制点。
没有把普通查询改名成强制求解，也没有取消近邻事件的拒绝保护。
每个 EVAS 请求时刻均精确存在，来源均为已接受状态；机制见[事件契约](../../../evas/docs/math/events.md)。

Spectre 的实际导出时刻未全部逐位命中 strobe 请求，部分偏差超过 16 ULP(stop)。
所有电压仍在原始记录的实际时刻验收，边界没有删除，没有插值或替换时间戳。
新增组合 runner 曾额外要求 Spectre 时间戳逐位命中，导致误判；其原始结果保留在收据中。
最终复算撤销的是这个不属于原标准的附加条件，原独立 checker 和数值预算未改。
因此，工程通过不等于证明 Spectre 精确命中了每个请求时刻。

实际运行采用基于 `6d23108d636514e7c8b296ad106b7652127f19ed` 的开发快照，
本目录随对应修复交付。收据保留运行时的 dirty 身份，不改写为事后提交身份。
服务器 release 内核 SHA256 为 `4a18493db7afcd38529efcb5bdf71d03a42ba40975b6182854b2cb4f18a47914`；
收据绑定源文件清单、构建、内核和输入哈希。Spectre 为 `21.1.0.509.isr12`。
四档请求与实际设置见[评测标准](../../../evas/docs/COMPARISON-METHODOLOGY.md#backend-controls)：
Spectre 固定 `traponly`，实际相对容差为 10⁻⁶ 或 10⁻⁹；没有把同名参数当作同一种精度保证。

原 80 配置为 76 通过、4 个 Spectre 名义积分超差，追加 4 配置通过。
源码、完整原生输出、执行日志及独立审查位于可见工作区
`runs/strobe-timer-fix-20261010/`，为 local-only；本目录只保留紧凑收据与维护脚本。
文件哈希不是公开数据下载地址。近邻原子事件、由保持状态决定的 timer 等原限制仍在。

复验原 12 配置沿用精度运行器；组合及诊断输入可分别冻结：

```sh
python3 -B experiments/backends/strobe/composition_run.py freeze runs/new-composition-inputs
python3 -B experiments/backends/strobe/composition_run.py freeze runs/new-timer-diagnostic --timer-diagnostic
python3 -B experiments/backends/strobe/timer_report.py runs/strobe-timer-fix-20261010 runs/new-timer-receipt.json
```

最后一条命令需要本地完整归档；它重新检查输入、原生文件、固定分母、构建绑定及全部实际观察。
正常组合和定时容差诊断分开计数，不改写旧收据。

## 首轮四个控制夹具

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
