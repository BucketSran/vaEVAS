# 采样到滤波的实际 Spectre 对照

**本批工程对照通过；18 条瞬时边界差异已接受，不再作为修复目标。**
四类工程组合在 Spectre 的三档配置和 EVAS 中均通过固定有限观测判据。
2026-10-10 用户接受 [SEF-TIMER-18](BOUNDARY.md#accepted-timer-18)；严格同刻诊断保留 FAIL，
不再单独阻塞本批工程验收，不宣称“边界已修复”或全节点逐点一致。
继续修复及新增实际 Spectre 证据见[边界与误差传播](BOUNDARY.md)；下文[旧收据](receipt.json)保留首次候选身份。
滤波输出同刻最大差从基础档的 **6.84 µV** 降为收紧档的 **0.103 µV**。
瞬时保持节点仍有事件窗内跳变侧差异，不能称为全节点逐点一致。
后续[独立误差分解](BOUNDARY.md#数学精度与回调时移的分开验收)区分名义数学误差、观察到的事件时移和剩余后端差异。
本批 EVAS 最大名义滤波偏差约 4.03×10⁻¹⁵ V；[18 条原记录](accepted-differences.json)全部保留。
后续[输入根自动细化](BOUNDARY.md#adaptive-root)用新 EVAS 内核重跑同源模型，复用已核验的实际 Spectre 数据。
宽 cross 容差下的部分高精度请求由拒绝转为满足预算，这与接受 timer 边界差异是两项独立结论。

本轮实测源码基于 main `ad6f3577`，实现与此报告同批交付，包版本仍为 0.14.0 / IR18。
首次候选构建、模型、判据和观察身份由[紧凑收据](receipt.json)绑定；合并状态与实验通过分开。
旧 27 条件、C1、#79 和 VCO 的结论不因本轮通过而改变。

## 比较结果

实际使用 Spectre **21.1.0.509.isr12**。相同 VA 和刺激运行 4 条件 × 3 配置，全部保留。
EVAS 在 Spectre 原生导出的 **52,200 个时刻**重新计算，不做插值或最近点替换。
另跑四条件各自的稀疏和密集查询，共 20 个 EVAS 请求。共同查询的完整解及事件记录逐位一致。

| 工程条件 | 基础档最大滤波差 | 收紧容差后 | 再缩小步长后 | 最终计数，Spectre 与 EVAS |
| --- | ---: | ---: | ---: | --- |
| 周期采样 | 4.238 µV | 0.1030 µV | 0.1026 µV | 4 / 4 |
| 时钟采样与复位 | 3.777 µV | 0.09574 µV | 0.09575 µV | 5 / 5 |
| 未完成边沿再次采样 | 6.837 µV | 0.08749 µV | 0.08749 µV | 8 / 8 |
| 双实例，取较大误差 | 3.484 µV | 0.07463 µV | 0.07463 µV | 两实例分别 4 / 4、3 / 3 |

边沿节点全行最大差为 0.082 nV。保持值在相同回调计数下、以及事件窗外的最大差也为 0.082 nV。
**保持值全行最大差仍为 1.15 V**：12 对配置中共有 18 个实例记录的计数相差 1，
全部位于执行前固定的 ±5 ps 事件窗内，窗外没有计数差异。
这反映跳变两侧的观察差异；原值和全行差值仍在收据中，未从分母删除。

固定工程预算是输出 100 µV、输入 10 nV、事件观测 ±5 ps。
保持值必须与当行计数指向的独立采样答案相符；边沿与滤波在全部原生点上检查。
完整判据与有理数分段、解析卷积答案见[独立契约](../../../evas/validation/sample_edge_filter/README.md)。
本批参与开发，不是未见的论文评价集，也不提供连续时间全轨迹误差证明。

## 容差的实际生效值

三档均为 `traponly`、`errpreset=conservative`，相同模型、strobe 请求与停止时刻。
`conservative` 将请求的相对容差再收紧 10 倍，下表以实际 transient 日志为准。
原 requested/effective mismatch 收据保留，不把它改写为请求完全匹配。

| 设置 | 请求 reltol | 实际 reltol | 实际 vabstol | 实际 maxstep |
| --- | ---: | ---: | ---: | ---: |
| base | 1e-5 | 1e-6 | 1e-7 V | 15.625 ns |
| tight | 1e-9 | 1e-10 | 1e-11 V | 15.625 ns |
| fine | 1e-9 | 1e-10 | 1e-11 V | 3.90625 ns |

EVAS 使用 `vabstol=1e-7 V, reltol=0`；两端内部控制含义不等价。
当前有限点说明收紧 Spectre 容差能明显减小滤波差，进一步缩小 maxstep 改善很小。
这不是所有设置都单调收敛的证明，也不是 EVAS 可调 LTE 的实现。

## 修复及保留的边界

基线不能执行 `transition → laplace_nd`，报 `unsupported_operator`。
实现为单个边沿驱动的一阶滤波增加独立历史：先沿旧边沿传播，再安装新采样目标；
延迟、边沿结束和中断处分段，复位保持量不重置滤波量。
输出查询不提交物理状态，过去观察使用保留快照。公式与误差责任见[算子手册](../../../evas/docs/math/operators.md#transition-filter)。

正式四条件采用常数非零初态，stop=8.5 µs。早期两个探针另行保留：
输入表达式 `initial_step` 赋值仍被编译拒绝；timer 恰在 stop=4 µs 的边界仍有认证拒绝。
它们未被重新标记为修复。原 `inputs/`、失败日志与修订后的 `inputs-v2/` 分别保存。

滤波反馈、多个历史输入、更高阶消费者及滤波输出触发 cross 不在新增支持范围。
首次候选遗漏了上游根窗口传播；后续已增加激活时间包围及零延迟积分前缀，详见[修复记录](BOUNDARY.md)。
任意重叠事件窗口仍是能力缺口，不授予完整组合时间包围资格。
复制 Spectre 精确回调落点不再是本批目标；初态/stop 探针的历史拒绝需按当前候选复验，不能随此次接受决定标为修复。
对应拒绝、失败回退、过去观察、目标区间和激活舍入有公开及 Rust 回归。

## 复验入口与材料

`run.py` 复用现有进程限制、工具身份检查、原生 PSF 解析和实际设置读回。
执行前固定输入，每次输出目录必须新建。远端串行，单次 90 秒，4 GiB 内存、32 MiB 文件、一个线程，无自动重试。

```sh
python3 -B experiments/backends/sample-edge-filter/run.py freeze runs/new-chain/inputs
# 在已有 Spectre 环境运行；profile 采用本机维护的实际工具配置。
python3 -B experiments/backends/sample-edge-filter/run.py spectre runs/new-chain/inputs --output runs/new-chain/spectre --profile /path/to/spectre-profile.json
python3 -B experiments/backends/sample-edge-filter/run.py evas runs/new-chain/inputs --output runs/new-chain/evas --kernel evas/rust_core/target/debug/evas-kernel --spectre-root runs/new-chain/spectre
python3 -B experiments/backends/sample-edge-filter/analyze.py runs/new-chain/spectre runs/new-chain/evas runs/new-chain/analysis.json
```

原始材料是 **local-only**，位于项目 `runs/sample-edge-filter-20261010/`。
Spectre 目录含 403 项已核验文件及旧判分；`analysis-final.json` 使用补强的非有限输入检查重新判分，未重写原结果。
`snapshot-final/`、`SOURCE_MANIFEST-final.json` 和 `BUILD-final.json` 绑定最终 EVAS 来源；
旧 `PROVENANCE.json`、`snapshot-v2/`、`evas-native/` 是中间执行记录，不能用作最终身份。
仓库内保留工具、独立契约及紧凑收据，不包含原始大波形，也不宣称原始材料已公开下载。
