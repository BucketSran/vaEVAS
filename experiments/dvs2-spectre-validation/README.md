# Spectre verification on thu-sui

## PR12 fixed timer comparison

`timer_reference.py` freezes a separate development comparison for EVAS 0.5.0
implementation `9a25a401`. It does not change the original 31-condition matrix.
The execution contract is written into each new run's `contract.json`; generated
VA, Spectre netlists, inputs, observation grids and checker sources are hashed
before either backend runs. `test_timer_reference.py` supplies independent
synthetic accept/reject controls, including locally legal values with no common
event history, missing/duplicate events, future stamps and endpoint windows.

The frozen batch has **12 configurations per backend**: four ordinary circuits
(two maxsteps, forward/reversed event and instance declarations), six endpoint
circuits (stop before/at/after the same event, two maxsteps), and two circuits
with 2,000 periodic events. There are **64 timer probe histories and 24 event
interaction probes per backend**, not 88 new benchmark conditions. Each
interaction probe contains two observable event histories. Ordinary probes cover
positive periods, omitted/zero/negative periods, zero/nonzero constant enables,
nonzero initialization with `timer(0)`, instance isolation, simultaneous timers
and events beyond stop. Interactions cover timer/timer and timer/cross before,
at and after the same nominal time, with voltage-state sampling.

The ordinary time unit is exactly `2^-30 s`; explicit timer tolerance is
`unit/1024`. Long probes use start `0.13 us`, period `7 ns` and tolerance `1 ps`;
their nominal answers are exact rationals of the submitted binary64 values.
Coarse/fine maxsteps are 5/0.5 ns (50/5 ns for long probes). Both backends use
reltol `1e-8`, vabstol `1e-10 V`; Spectre also uses iabstol `1e-14 A` and
`traponly`. Spectre exports every accepted point without strobe; EVAS additionally
uses different output grids in the forward/reversed configurations.

Every exported input and output point is retained. Counts, sampled clocks and
held data must admit one ordered event history within the independent nominal
windows. The conditional voltage allowance is `1e-8 V`; this is an assumed
finite-observation screen, not a measured physical observation-error bound.
Timer windows are symmetric, cross windows one-sided. Endpoint windows are
not clipped to stop: an event may remain unobserved if its allowed window extends
beyond stop. Same-time voltage-state reads are classified against EVAS's
pre-event-snapshot candidate; a different valid state is reported explicitly,
not silently accepted as compatibility or labelled an LRM violation.

Budget: at most 12 Spectre circuit attempts in one fresh run, serial, one pinned
CPU, 90 seconds per attempt including a 30-second license wait, no in-place retry.
Any changed-input follow-up receives a new identity and preserves the old attempt.
This comparison cannot establish full timer support, continuous-time accuracy,
dynamic-parameter semantics, atomic rollback inside Spectre, or a performance
advantage. The other three timed operators are outside this batch.

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_timer_reference.py' -v
python3 -B experiments/dvs2-spectre-validation/timer_reference.py build runs/NEW-TIMER
python3 -B experiments/dvs2-spectre-validation/timer_reference.py evas runs/NEW-TIMER --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/timer_reference.py spectre runs/NEW-TIMER --spectre-profile /path/to/private-profile.json
python3 -B experiments/dvs2-spectre-validation/timer_reference.py check runs/NEW-TIMER --output runs/NEW-TIMER-analysis.json
```

The Spectre action runs on the configured Linux host. Transfer the frozen inputs
and the exact checker dependencies to a fresh checkout layout there; preserve
and verify its returned file manifest before analysis. Private profiles, raw
waveforms and full logs remain outside Git.

The first combined run revealed an EVAS event-ordering rejection. A separate
`build ... --isolate` follow-up preserves all four ordinary configurations and
their probe parameters, but splits each into three circuits: timers (including
timer/timer interactions), neighboring timer/cross events, and simultaneous
timer/cross events. It adds at most 12 Spectre attempts under the same per-run
budget. The original rejection remains in the report. This follow-up is
development diagnosis after observing the first result, not an unseen test set;
no acceptance thresholds or EVAS implementation are changed. The first checker
is reproducible at commit `6aa43ad`; each run retains its exact source hashes.

Run `-01` initially classified two Spectre endpoint observations as invalid:
PSF printed the final time one binary64 ULP above the requested stop, and the
input evaluator rejected this outside its closed knot domain. The corrected
adapter applies the PWL source's constant endpoint extension while preserving
the raw timestamp, original coverage gate, voltage allowance and event windows.
A calibration accepts this rounding case but rejects wrong input values and
out-of-range final times. Reanalysis is explicit: `check` with
`--frozen-source-root /path/to/extracted-original-input-archive` verifies the
original source snapshot and records both original and current checker hashes.
The original analysis remains archived; this is a checker correction, not a
new Spectre execution or a changed event acceptance target.

## Original 31-condition comparison

This experiment implements the 16 conditions in the seven
[new case cards](../../evas/validation/NEXT_CASE_CARDS.md), reruns 14 unchanged
v1 conditions, and runs a separate standard-array revision of the v1 lowpass
condition. There are **31 conditions and 62 configurations** across two settings.
**Completed on 2026-09-28: all 62 runs produced waveforms and all 62 met the
frozen finite-observation targets.** Spectre version: `21.1.0.509.isr12`.
No execution failures, timeouts, numerical violations or unresolved finite
checks occurred. Formal observation qualification remains I.

The separate [PR7 cross comparison](#pr7-cross-小规模对照) below uses eight
development conditions. Its results do not change this 31-condition denominator.

[PROTOCOL.md](PROTOCOL.md) is frozen before execution and describes inputs,
resource limits, targets, observation requirements, conditional history checks,
and the distinction between finite checks and formal qualification.

- [run_suite.py](run_suite.py) builds stimuli, netlists and the immutable manifest.
- [remote.py](remote.py) verifies inputs and runs Spectre serially without retries.
- [check_results.py](check_results.py) checks archived waveforms against independent
  mathematical answers, retaining every accepted point.
- [test_checks.py](test_checks.py) supplies eight calibration methods containing
  controls for all 16 new conditions, hand anchors, seven semantic fault classes,
  wrapped-range/whole-cycle faults, malformed observations and uncertainty bands.

The sampler source is intentionally shared by E2 and C1; C2 packages that same
sampler and the standard-array lowpass as two distinct modules. These are new
condition identities, with full instance declarations and all input/intermediate/
output nodes saved. The former v1 `v6-main` source remains frozen; `v6-standard`
is its explicitly identified source revision, not an additional 32nd condition.

Reproducible local checks:

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p 'test_*.py' -v
python3 -B evas/validation/check_design_math.py
python3 -B scripts/verify_validation_version.py
```

Build inputs only into a fresh directory:

```sh
python3 -B experiments/dvs2-spectre-validation/run_suite.py runs/NEW-RUN-input
```

The remote tool profile stays private. Execution, transfer, and reanalysis must
use the new run identity and preserve its input/output manifests. Results do not
qualify timestamp semantics or between-export behavior; formal DVS status is I.
This batch does not execute any other backend, historical variant suite or model
API, and does not modify EVAS or the v1 snapshot.

## 本轮结果

| 范围 | 条件数 | 基础设置 | 细化设置 |
| --- | ---: | ---: | ---: |
| v1 的 14 个原条件，加标准语法低通修订 | 15 | 15/15 | 15/15 |
| E1：方向事件计数 | 3 | 3/3 | 3/3 |
| E2：初始高电平与复位恢复 | 3 | 3/3 | 3/3 |
| C1：有状态实例隔离 | 3 | 3/3 | 3/3 |
| C2：低通后采样 | 1 | 1/1 | 1/1 |
| D1：积分、保持复位与释放 | 2 | 2/2 | 2/2 |
| D2：常频/变频相位与包裹 | 2 | 2/2 | 2/2 |
| S1：多输入与贡献累加 | 2 | 2/2 | 2/2 |
| **合计** | **31** | **31/31** | **31/31** |

表内“通过”表示成功执行且全部合格导出点满足预先固定的有限观测判据，
不表示正式 DVS P。两档共检查 **1,333,719 个时间点**；最大导出间隔约
1 ns。62 份实际生效的步长、最大步长、停止时间、误差容限和积分方法均与请求一致。
执行用时之和约 608 秒，包含编译与启动，不作为仿真器性能比较。

共同历史检查共涉及 40 条输出历史（包含同一条件的多输出，不另算测试条件），
在 B=0 与候选 B=0.25 mV 两个场景均取得共同历史见证。积分器的两条件、两档
也均取得相应有限数值见证。几个有独立解析目标的最大观测误差为：

| 量 | 最大误差 | 固定目标 |
| --- | ---: | ---: |
| C2 低通中间节点 | 0.1743 μV | 600 μV |
| D1 带复位积分输出，基础设置 | 48.73 μV | 1,000 μV |
| D2 累计/包裹相位 | 3.444e-7 周期 | 1e-4 周期 |
| D2 正弦电压 | 1.731 μV | 1,000 μV |
| S1 加权输出 | 9.437e-16 V | 1e-3 V |

上述误差是导出值相对解析答案或所列合法共同见证的误差，未加入未经证明的
物理观察误差界。D2 两条件分别观测到 2、4 次包裹；E1 的网格平移对照不证明
后端内部实际走过“精确零点”分支。其余后端的新增条件和旧 126 个变体未在本批运行。

所有 62 份日志均有相同的非致命 `VACOMP-2435` 提示：旧环境变量
`CDS_AHDLCMI_ENABLE` 不再受支持，Spectre 使用默认编译 C 流程。
未修改共享环境或放宽阈值；该提示与原始日志一并保留。

## 证据与复核

- [逐配置分析](results/analysis.json)：输入/输出检查、解析误差、共同历史见证和正式资格状态。
- [归档收据](results/RECEIPT.json)：版本、工具/输入/原始归档/分析哈希、运行预算和汇总。
- [实际设置核对](results/effective-settings.json)：62 份日志提取结果和请求匹配情况。
- 原始输出位于仓库忽略目录 `runs/dvs2-spectre-20260928-01/`，压缩包为
  `runs/dvs2-spectre-20260928-01.tar.gz`；thu-sui 的任务私有运行区另保留压缩归档。
  已核对压缩包 SHA-256 和清单中的 **1,216 个文件**，不将原始机器日志提交到仓库。
- 输入清单在启动前冻结，原始模型、网表、分析代码和协议快照均进入归档。
  [report.py](report.py) 是运行后整理设置与收据的程序，单独记录哈希，未改变判定器。
- 新判定器 8 项校准方法、共享历史判定器 17 项校准/适配方法均通过；设计算术检查
  和 v1 的 36 个 Git 工件、4 个快照工件、13 个原始输入身份检查通过。

原始证据保持只读，复核写入一个新的外部输出路径：

```sh
python3 -B experiments/dvs2-spectre-validation/check_results.py \
  runs/dvs2-spectre-20260928-01 runs/NEW-ANALYSIS.json
```

本次确认当前 31 条件在该版本 Spectre、这两档设置下均可执行且观测达标。
完整输入误差、时标语义、未采样区间和其他行为覆盖的资格工作仍未完成；不据此
外推所有 Spectre 版本、所有 Verilog-A 模型或 EVAS 的通过情况。

## PR7 cross 小规模对照

2026-09-29，EVAS 0.4.4 在本机运行，Spectre `21.1.0.509.isr12` 在 thu-sui
运行相同 DUT 和连续 PWL 激励。[cross_reference.py](cross_reference.py) 提供
8 个开发条件：双向、仅上升、37 ps 平移、断点穿越与相切、初始高电平、内部反馈、
收紧时间容差、收紧表达式容差。每条分别使用 100 ns / 7 ns 最大步长，共每后端 16 组。
该 DUT 不含 `transition`，不替换原 E1，也不是新的未见确认集。

事件块累加计数并采样线性时钟电压；检查器根据独立声明的 PWL 段，用精确有理数
计算根及允许窗口 `min(ttol, tol/abs(slope))`，再检查计数和保持电压。
两个后端均接受同一判据；不以两者相等作为正确性的定义。
预先固定的电压观测余量为 `1e-8 V`（时钟上约 10 fs），这是条件假设，
不是已证明的物理观测误差界。有限采样和保持值也不证明完整连续事件历史。

| 固定判据结果 | EVAS | Spectre |
| --- | ---: | ---: |
| 普通穿越等 7 条件 × 两档 | 14/14 | 14/14 |
| 断点穿越与相切 × 两档 | 2/2 | 0/2，事件次数不同 |
| 合计 | 16/16 | 14/16 |

最后两组预期在 0.5、2.5 µs 穿越时各触发一次，忽略 1.5 µs 的同侧相切。
Spectre 两档都额外在 1.5 µs 触发，最终计数为 3，EVAS 为 2。
这表示 **当前 EVAS 相切契约与 Spectre 实测行为不一致**，不能解释成 Spectre 错误
或 EVAS 更准确，也没有通过修改判据消除差异。

另外两次成功的方向诊断使用 `u: 0.6 → 0.5 → 0.6 V`，谷底在 1.5 µs，
guard 为 `scale*(V(u)-0.5)+offset`，同一网表含七个独立实例：

| guard | 双向次数 | 上升次数 | 下降次数 |
| --- | ---: | ---: | ---: |
| `V(u)-0.5` | 1 | 0 | 1 |
| `-(V(u)-0.5)` | 1 | 1 | 0 |
| `V(u)-0.5+1e-6` | 0 | 未运行 | 未运行 |

两档一致，观测触发时刻均为 1.5 µs，符合“按接近零的方向触发”的现象。
最低点仍为正、但小于表达式容差的实例没有触发；因此不能简单用容差带模拟这个行为。
这里没有内部 guard 记录，不能确定内部零值分类或舍入机制，也未把这两次诊断
加入基线通过分母。首次诊断两次均因 VA 的 `.5` 字面量语法被拒绝；修正为 `0.5`
并将方向参数声明为整数后，在新目录重跑。失败记录保留，未作为波形结果使用。

普通穿越中，保持电压反推出的 Spectre 最大延迟约为：默认 25 ps、内部节点斜率
加倍时 12.5 ps、收紧 `ttol` 时 0.5 ps、收紧 `tol` 时 0.25 ps。
这些值满足固定窗口，支持分别核验两项容差的设计；它们不证明通用的“半窗口”算法。
EVAS 无须复制相同延迟，但仍须证明自身的根定位误差满足声明容差。

[完整收据](results/cross-reference-0.4.4.json) 保存每组结果、源码/内核/检查器哈希、
实际设置和诊断 DUT。基线 16 次 Spectre 执行均成功，无超时；16 份生效设置匹配，
只出现既有非致命 `VACOMP-2435`。连同诊断共 20 次电路执行：18 次产出波形，
2 次语法失败。原始归档位于忽略目录 `runs/pr7-spectre-contract-20260929/`，
thu-sui 任务私有区另有副本；主归档 296 个文件、诊断归档两批共 54 个文件的哈希均已核对。
执行耗时含启动与编译，不作为性能比较。

复现时先运行检查器校准，再冻结新目录；将源码、检查器依赖和冻结目录复制到
已有 Spectre 环境后执行 `spectre` 子命令，私有工具 profile 不进入仓库。
回传完整结果后在原源码版本重新分析：

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p test_cross_reference.py -v
python3 -B experiments/dvs2-spectre-validation/cross_reference.py build runs/NEW-CROSS
python3 -B experiments/dvs2-spectre-validation/cross_reference.py evas runs/NEW-CROSS --kernel evas/rust_core/target/debug/evas-kernel
python3 -B experiments/dvs2-spectre-validation/cross_reference.py spectre runs/NEW-CROSS --spectre-profile /PRIVATE/profile.json
python3 -B experiments/dvs2-spectre-validation/cross_reference.py check runs/NEW-CROSS --output runs/NEW-CROSS-analysis.json
```

四项校准方法包含手算锚点、合法延迟、共同错误、缺失/错序/非有限观测等控制。
当前结论只涉及这些限定条件；相切语义仍须 review，不宣称完整 Spectre 兼容。

## PWL 触零边界实验

[cross_touch.py](cross_touch.py) 单独检查步长、时刻平移、容差与触零次数的关系，
EVAS 保持 0.4.4。每组有三路 PWL 电压，从 0.6 V 降到 0.501 / 0.500 / 0.499 V，
再回到 0.6 V。每路分别监测正、负 guard 和双向/上升/下降三个方向，
共 18 个独立监测实例。事件块保存次数、线性时钟电压和当次 guard 采样值。

| 因素 | 设置 |
| --- | --- |
| 谷底时刻 | 1.5 µs；整个波形平移 37 ps，前段补恒定值 |
| 最大步长 | 100 ns、7 ns |
| 默认事件容差 | `ttol=100 ps`、`tol=10 µV` |
| 只收紧时间容差 | `ttol=1 ps`、`tol=10 µV` |
| 只收紧表达式容差 | `ttol=100 ps`、`tol=0.1 µV` |

两时刻 × 两步长 × 三容差，共 **12 个配置，每后端 216 条监测历史**。
谷底高于阈值的实例预期没有事件；低于阈值的实例预期双向两次、每个单方向一次。
两次真实穿越间隔约 29.7 ns，大于最大时间容差 100 倍；解析根以冻结 binary64
PWL 输入的精确有理数独立计算。恰好触零的六个实例只分类观测为“不触发、到达方向、
离开方向、两个方向或其他”，不先规定哪一类正确。

输入、检查器和 12 次 Spectre 执行预算在运行前冻结；每次使用一个固定 CPU，
90 秒墙钟上限、30 秒许可证等待，不自动重试。固定电压观测余量仍为 `1e-8 V`，
检查所有导出点的有限性、输入、计数历史、保持时间见证和事件 guard 采样值范围。
触零分类不是正式语义资格，公开的 guard 采样也不等于 Spectre 内部迭代记录。

2026-09-29 的新批次 `pr7-touch-boundary-20260929-01` 已完成：本机 EVAS 和 thu-sui
Spectre 各执行 12 个配置。两者的 144 条非零谷底控制历史全部满足冻结判据；
各自另有 72 条恰好触零的诊断历史。全部配置的分类一致：

| 谷底 | EVAS：双向 / 上升 / 下降 | Spectre：双向 / 上升 / 下降 |
| --- | --- | --- |
| 高于阈值，正 guard | 0 / 0 / 0 | 0 / 0 / 0 |
| 恰好触零，正 guard | 0 / 0 / 0 | 1 / 0 / 1 |
| 恰好触零，负 guard | 0 / 0 / 0 | 1 / 1 / 0 |
| 低于阈值，两种极性 | 2 / 1 / 1 | 2 / 1 / 1 |

高于阈值的负 guard 同样无事件。Spectre 所有触零事件的公开 guard 采样值均为 0，
没有“到达一次、离开再一次”的双重计数。其基础档导出 70–76 点、细化档 461–466 点，
导出网格明显不同，但触零次数和方向保持一致。普通穿越的最大观测延迟约为默认
50 ps、收紧时间容差后 0.5 ps、收紧表达式容差后 0.743 ps，均满足各自窗口。

因此，在本次 PWL 范围内，单纯减小步长没有消除差异，结果支持到达零值时的事件规则
与 EVAS 不同。但全部触零点仍是显式 PWL 断点，尚未排除断点命中的作用，也未测试
没有显式断点的光滑极小值；不把观察模式当作 Spectre 内部算法的证明。本次没有修改
EVAS 运行时语义，也没有增加原 31 条件的分母。

[逐配置收据](results/cross-touch-0.4.4.json) 保存计数、方向、事件采样、设置和完整身份。
12 次 Spectre 执行均成功，无超时；只出现 12 次既有 `VACOMP-2435`。
已核对原始归档中 812 个文件，另将本机 13 份 EVAS 工件按相同输入身份汇集分析。
私有原始材料位于忽略目录 `runs/pr7-touch-review-20260929/`；远端另保留原始压缩包。

报告处理有两项明确修复，未修改事件判据、未增加电路执行：共享测试发现与旧 pilot
同名的 `report.py` 导入冲突，发布脚本改为按文件路径加载所属模块；平移后的日志把
停止时间 `3.000037 µs` 显示为 `3.00004 µs`，冻结分析先报告 6 次设置不匹配。
重分析按日志显示精度区间核对 stop，再要求波形末点与请求值在原定 `1e-18 s`
界限内一致，其余设置仍按原阈值核对。六份波形末点均为请求值；原始误报和修复后报告
分别保留。所有波形、根和事件检查仍使用归档中的冻结函数。
新检查器原有 4 项校准、后补 2 项元数据校准均通过，目录内共 18 项测试通过。

复现新批次：

```sh
python3 -B -m unittest discover -s experiments/dvs2-spectre-validation -p test_cross_touch.py -v
python3 -B experiments/dvs2-spectre-validation/cross_touch.py build runs/NEW-TOUCH
python3 -B experiments/dvs2-spectre-validation/cross_touch.py evas runs/NEW-TOUCH --kernel evas/rust_core/target/debug/evas-kernel
# 将冻结目录及检查器依赖复制到已有 Spectre 环境后执行：
python3 -B experiments/dvs2-spectre-validation/cross_touch.py spectre runs/NEW-TOUCH --spectre-profile /PRIVATE/profile.json
# 汇集同一输入身份的两后端结果后：
python3 -B experiments/dvs2-spectre-validation/cross_touch.py check runs/NEW-TOUCH --output runs/NEW-TOUCH-analysis.json
```

## 孤立触零契约回放（0.4.5）

用户审阅上述实验后，EVAS 0.4.5 将内部 PWL 孤立零点定义为到达方向触发一次，
离开不再触发。`cross_touch.py check --require-arrival` 启用显式版本契约
`isolated-pwl-zero-arrival-v1`：正 guard 的双向／上升／下降次数为 `1/0/1`，
负 guard 为 `1/1/0`。逐点检查计数窗口、方向、保持时间见证和 guard 采样；
原始 `inspect` 诊断模式、非零谷底判据和 `1e-8 V` 观测余量均保持不变。
新增 3 项校准方法，接受到达规则，拒绝漏事件、离开方向、双触发、过早或过晚计数、
错误保持时间及 guard 值。目录内共 21 项校准方法通过。

`pr7-touch-arrival-20260929-02` 在运行前固定该契约、检查器和输入身份，
新执行本机 EVAS 的 12 个配置，**没有新执行 Spectre**。复用前述 thu-sui 批次，
核对原始归档哈希及 812 份文件；新旧 85 份模型、网表和条件文件逐字节一致。
在新目录中重判 12 份归档 Spectre 波形及新 EVAS 输出：

| 有限观察历史 | EVAS 0.4.5 新执行 | Spectre 归档重判 |
| --- | ---: | ---: |
| 高于阈值及低于阈值控制 | 144 / 144 | 144 / 144 |
| 孤立触零、两种极性和三种方向 | 72 / 72 | 72 / 72 |

全部 12 配置的计数与方向一致。作为反例，同一新检查器重判旧 EVAS 0.4.4：
144 条普通控制仍通过，72 条触零历史中 48 条应触发而未触发；另外 24 条本就要求零次事件。
这不是重写旧版的诊断结论，而是按获审阅的新契约单列检查结果。

[0.4.5 收据](results/cross-touch-0.4.5.json) 保存新旧输入、构建、检查器及波形哈希，
并逐配置记录计数和方向；原始运行、冻结契约及完整重判输出保存在忽略目录
`runs/pr7-touch-arrival-20260929-02/`。只增加本次开发回归证据，不增加原 31 条件分母。
所有触零点仍为显式 PWL 节点；不证明光滑极值、零平台、停止时刻触零、完整 DVS 资格或性能优势。

对同一输入身份汇集的两后端输出启用新契约：

```sh
python3 -B experiments/dvs2-spectre-validation/cross_touch.py check runs/NEW-TOUCH --require-arrival --output runs/NEW-TOUCH-arrival.json
```

## 零平台和停止点边界（0.4.6）

`cross_boundaries.py` 独立冻结 21 种输入、3 个方向及 6 个配置：maxstep 为 100/7 ns，
每档搭配 nominal（ttol=100 ps、tol=10 µV）、time_tight（1 ps、10 µV）和
expression_tight（100 ps、0.1 µV）。同一 VA 探针保存计数、事件时钟和 guard；
21 种输入包含终点到零及终点后延伸、同侧/异侧平台、初始/终端平台、20 ps 短平台、
恒零输入，并以近零非零平台、普通穿越和已审阅的孤立零点作对照。

运行前固定候选规则：非零到零按到达方向触发一次，停留及离开不触发；终点输出可见提交后的状态。
边界结果标为 candidate-consistent/inconsistent，不预设哪个仿真器正确。
检查器逐点检查次数窗口、方向、保持时间与输入重建的一致性、guard 容差及初始状态，
观测余量为原定 `1e-8 V`；4 项合成校准覆盖缺失/重复/错误方向事件和错误历史、采样。
这属于条件性的有限观察判据，不是对内部步进或完整 LRM 的证明。

`cross-boundaries-20260929-01` 的 6 次 Spectre 均在编译期因 `.5` 字面量被拒绝
（VACOMP-1795），未产生瞬态结果。保留其输入、原始日志和身份；探针仅改为 `0.5` 后，
以 `cross-boundaries-20260929-02` 重新冻结相同输入和判据。该新批次 6 次全部完成，
单 CPU、串行、每次 90 秒上限、license 等待 30 秒，批次内不重试；两批总计 12 次 Spectre 尝试。
核对新批次原始归档的 110 份文件、有效设置及高精度停止时刻后：

| 有限观察历史 | EVAS 0.4.6 新执行 | thu-sui Spectre 新执行 |
| --- | ---: | ---: |
| 零平台/停止点边界（15 输入 × 3 方向 × 6 配置） | 270 / 270 | 270 / 270 |
| 近零、普通穿越、孤立触零对照（6 × 3 × 6） | 108 / 108 | 108 / 108 |

两后端计数和方向一致；该结果支持本轮 EVAS 到达规则扩展，不能推广到光滑极值、动态/
非线性轨迹或有状态反馈的 guard。EVAS 0.4.5 对首批相同数值输入的 6 个组合请求均
显式返回 `unsupported_cross`，这是组合请求被拒绝，不能算成 378 条逐探针失败。
原 31 条件及其支持数量不变。

[整理后的收据](results/cross-boundaries-0.4.6.json) 保存冻结输入、检查器、内核、原始归档及
逐配置结果身份，原始记录在忽略目录 `runs/cross-boundaries-20260929-01/` 和 `-02/`。
复现实验应使用新的输出目录；运行前检查收据里的预算与使用权限：

```sh
python3 experiments/dvs2-spectre-validation/cross_boundaries.py build runs/NEW-BOUNDARIES
python3 experiments/dvs2-spectre-validation/cross_boundaries.py evas runs/NEW-BOUNDARIES --kernel evas/rust_core/target/debug/evas-kernel
python3 experiments/dvs2-spectre-validation/cross_boundaries.py spectre runs/NEW-BOUNDARIES --spectre-profile /path/to/private-profile.json
python3 experiments/dvs2-spectre-validation/cross_boundaries.py check runs/NEW-BOUNDARIES --output runs/NEW-BOUNDARIES-analysis.json
```
