# 求解成本与内核边界

本目录测量静态求解、瞬态推进及构建成本。测量用于选择优化；不增加原 31 条件的分母，也不证明相对 Spectre 更快。

长期候选由 [issue #138](https://github.com/BucketSran/vaEVAS/issues/138) 保留。
本次输入共享优化交付后，速度优化阶段收尾；待功能正确性完善后再考虑其余候选。

<a id="direct-input-sharing"></a>

## 只读输入共享

`DirectInput` 将不可变点列和误差区间改为共享数组，减少候选与回放中的复制。
数值运算、认证、事件推进及历史验收保持原样。[本次收据](direct-input-sharing.json)
对应 main `040df8ed` 上的[已审查源码检查点](https://github.com/BucketSran/vaEVAS/commit/4dafbbb1108d4d485248c1e2cb426e8c64ea72ab)。
收据保留测量时的本地身份；发布前核对了源码与检查器哈希，原测量证据继续适用。

合成案例含 4097 个三角波拐点和 8193 个观察点，每个半段都有观察，覆盖非零积分值。
两批均交替运行基线与候选各五次，正式时间关闭诊断：

| 批次 | 基线端到端 ms，中位数及范围 | 候选端到端 ms，中位数及范围 |
| --- | ---: | ---: |
| 七案例批次中的长三角波 | 548.37，426.12–1063.25 | 225.64，212.68–312.37 |
| 长三角波单独复测 | 508.84，450.90–578.90 | 281.16，218.42–374.54 |

机器同时有其他任务，首批负载明显升高，所有慢样本均保留。第二批确认了本例收益，
但不据此承诺通用加速比例。另六例的时间范围重叠，没有测到稳定改善或退化。
峰值 RSS 也不足以支持通用节省内存的结论，减少复制不等于同比降低峰值内存。

诊断复测中，`history.clone` 中位耗时从 173.34 ms 降到 3.45 ms。
逻辑克隆仍为 24576 次，候选、求解和认证次数保持一致；共享的是输入数组。
该阶段未覆盖所有输入复制，阶段之间也有包含关系，不能相加或用它推算全部收益。

160 次配置执行全部完成。每例的新旧内核及诊断开关响应逐字节一致，包括误差区间和事件。
三角波另用精确有理数积分检查包含性，并按请求的原电压预算验收区间宽度。
校准反例确认，输出接近但区间漏掉答案时仍失败。229 项 Rust 和 157 项相关 Python 测试通过，
另有一项既有 Rust 测试保持忽略；覆盖候选隔离、回滚重试、复位、区间精度和拒绝。

两份已核验哈希的实际 Spectre 记录用于重跑同源码 LP-nd/LP-np 对照。
原 1 mV 有限观察标准保持，双方分别通过独立答案检查，每例 20 个严格同时间点的差异也达标。
这是既有滤波输入路径的有限对照，不证明一般波形精度，也没有测量相对 Spectre 的速度。

生成长输入请求时，在下面的瞬态基准命令前设置 `EVAS_BENCH_CASE=pwl_idt`
和 `EVAS_BENCH_OUTPUTS=8193`，小规模对照使用 129。该可选案例要求观察数为
`2*2^k+1` 且 `k>=2`；未设置案例时仍运行原五例。检查器校准命令为：

```sh
python3 -B -m unittest discover -s experiments/performance -p 'test_*.py' -v
```

## #138 恢复轮分析（2026-10-17）

issue #138 恢复探索的首轮只读分析：[热点重测与切片排序](analysis-20261017/2026-10-17-evas-acceleration-analysis.md)
（main `e2c7aac7`：nonlinear_idt ≈ 220 ms 主导；trial 全量 clone、事件全量重建、非线性区间
Jacobian 每步重算三处代码证据）、[外部加速调研](analysis-20261017/2026-10-17-external-acceleration-survey.md)
（Spectre-X/PrimeSim/Xyce/KLU/batched BLAS 做法与仿射算术等数学方向）与
[候选扩展提案](analysis-20261017/2026-10-17-issue138-extension-proposal-draft.md)（E1–E5）。
实施切片以 PR 为准（P03 → #205、P05 → #207），报告只保留分析与依据。

<a id="history-entry-sharing"></a>

## 算子条目写时复制（存档，代码未合入）

> **状态：存档，代码未合入 main。** 以下是 #138 P14 第二切片的测量结论；代码改动保留在分支
> `codex/p14-history-sharing-slice2`（[PR #212](https://github.com/BucketSran/vaEVAS/pull/212)，草稿）。
> 该切片没有可测的端到端收益，且会与未合并的 PR #208 在 `operators.rs` 的历史复制计费处冲突，
> 所以等 PR #208 合入后，确有需要时再在其上重放。下文所说的 `Arc` 共享与
> `history_entry_copy_on_write` 计数器只存在于该分支，当前 main 没有。


P14 第二切片把 `Operators` 的 `entries` 改为逐条目 `Arc` 共享，trial 只在真正
就地修改某条目时才深拷贝该条目（`Arc::make_mut`），并把构造后不可变的
`changes_on_advance`、`direct`、`isolated_parameters` 改为共享切片。
数值运算、认证、事件推进及历史验收保持原样。[本次收据](history-entry-sharing.json)
记录配对结果；原始证据在本仓库忽略的 `runs/performance-p14-20261017/`。

六例（pwl/idt/pwl_idt/nonlinear_idt/timer/cross，各 8193 观察点）交替五轮共 120 次配置
（最终内核），另有同规模探索批保留在原始证据中。每例新旧内核及诊断开关的完整
JSON 响应逐字节一致（含事件与误差区间）；三角波案例由检查器用精确有理数积分验收包含性。
诊断计数确认求解与认证次数不变；新增 `history_entry_copy_on_write` 计数器报告实际发生的
条目深拷贝（上述六例均为 0，即全部条目在 trial 间共享；带 idt 复位的路径由 Rust 回归覆盖）。

端到端计时没有测到稳定差异：上一切片后每次 trial 的 `base.clone()` 只剩约
0.05–0.09 ms（`history.clone` 全程约 1–2 ms，占端到端约 1%），消除这部分复制
低于本机波动，按验收规则记为无可测差异，不宣称提速。主机同期有其他任务
（负载 5–10），各例范围互相重叠、中位数方向不稳定，全部慢样本保留在收据中。
当前 pwl_idt 剩余热点在 trial 内 `settlement::prepare` 重建整个 `Circuit`
（`circuit.prepare` 每次 trial 约 1.1 ms），属于 P05（事件后重建）范围，不在本切片内。

## 固定矩阵复用与稀疏消元实测

[紧凑收据](results.json)保存配对结果、阶段、次数、内存和执行身份。相同请求与容差在基线/候选 release 内核上各运行五次独立进程，交替顺序。诊断开关及两个内核的输出逐字节相同，并通过基准内的独立答案。

| 请求 | 基线端到端 ms | 候选端到端 ms | 候选范围 ms | 分解次数（基线→候选） |
| --- | ---: | ---: | ---: | --- |
| random-1024 | 1671.45 | 329.14 | 328.13–330.52 | 1→1 |
| grid-256 | 17.69 | 17.37 | 15.40–62.92 | 1→1 |
| chain-1024 | 35.42 | 35.55 | 34.20–35.79 | 1→1 |
| idt-4097 | 66.66 | 63.84 | 62.80–64.32 | 16385→1 |
| nonlinear_idt-4097 | 110.51 | 105.36 | 104.74–109.19 | 16385→1 |
| timer-4097 | 23.50 | 22.58 | 20.54–24.71 | 33→1 |
| cross-4097 | 20.21 | 20.10 | 19.38–22.03 | 18→2 |
| pwl-131073 | 473.68 | 466.09 | 462.56–477.22 | 1→1 |

随机 1024 阶矩阵输入有 5,106 个非零项，LU 保存 149,102 项，消元填充更新是主要成本。本轮用一次 `BTreeMap::entry` 查找完成读改写，仅在新填充或精确抵消时更新活动列。主元、缩放、列次序和减法顺序保持不变。`sparse_ordering` 只计选择下一列，列度维护仍在 `sparse_elimination` 内。

积分候选与回放现在可共享接受帧的只读 LU。节点、驱动/未知量顺序、行数及全部系数的 binary64 位必须相同。每次仍计算当前 RHS、验收原关系与历史误差；非线性 Jacobian 不使用这个缓存。

阶段包含子阶段，不能相加。输出点、候选次数与积分器内部步数分开记录。矩阵行/列/nnz 和 LU 项数按分解累加，不是峰值。历史复制只统计调用次数与逻辑算子槽数，尚无分配/复制字节计数。短请求受进程启动和计时波动影响；诊断有额外成本。这些结果仅适用于固定合成工作负载。

## 重跑

先在收据指定的两个提交分别构建 release 内核。测量时不要同时构建或运行测试。从仓库根目录运行，输出目录必须不存在：

```sh
mkdir -p runs/performance/requests
EVAS_BENCH_SAMPLES=64 EVAS_BENCH_REQUESTS="$PWD/runs/performance/requests" cargo bench --locked --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_OUTPUTS=4097 EVAS_BENCH_REQUESTS="$PWD/runs/performance/requests" cargo bench --locked --manifest-path evas/rust_core/Cargo.toml --bench transient_solver
python3 -B experiments/performance/profile_requests.py --kernel /absolute/candidate/evas-kernel --baseline-kernel /absolute/baseline/evas-kernel --baseline-revision BASE_SHA --requests runs/performance/requests --out runs/performance/paired --repeats 5
python3 -B experiments/performance/measure_build.py --output runs/performance/build --repeats 2
```

20 个静态用例覆盖链、环、星、网格、固定种子网络、稠密与多项式。答案来自递推、构造的精确根或独立二分。五个瞬态用例检查斜坡、解析积分、`1/(1+t)` 及手算事件时刻。额外长斜坡由同一 PWL 请求将 `output_times` 改为 `[i/131072 for i in range(131073)]`。
库内静态基准另外用默认 512 个重复 RHS，瞬态用 129 与 4097 点各测五轮。不同点数的结果不相减作为传输成本。

完整边界为 Python 序列化 → 启动进程 → 内核读/解析/求解/编码 → Python 解析。不包含 VA 编译、磁盘归档、答案检查或诊断 sidecar 解析。macOS 用 `time -l` 测内核子进程峰值 RSS；Python highwater 是整个测量进程截至该次的峰值，含先前用例。两者不能相加当作同时峰值。其他平台缺少指标时为 null。

原始请求/stdout/日志/sidecar 保存在本地 ignored 归档。GitHub 保存摘要与重跑工具；哈希不代替可下载的原始材料。收据绑定固定 Git 源码、实际源码哈希与内核身份。

## 非线性历史区间复用

[PR #205](https://github.com/BucketSran/vaEVAS/pull/205) 将已接受非线性步的区间求值按步身份和窗口位级键复用。基线 `e2c7aac7`，行为候选 `f0d29720`，冻结 release 内核及请求身份见[紧凑收据](nonlinear-history-range-reuse.json)。这补充旧 kernel-only 微基准，不能把两种边界的耗时相减。

使用维护中的 `profile_requests.py`，新旧各五轮，逐轮交换先后顺序。正式计时关闭诊断，另跑开启诊断的等量请求核对完整响应和路径计数。边界含 Python 序列化、进程启动、内核读入/解析/求解/编码和 Python 解析，不含 VA 编译、答案检查或归档写盘。macOS `time -l` 记录内核子进程峰值 RSS；表中为五轮最大值，未与 Python 全进程 highwater 相加。

| 案例 | 基线完整请求 ms，中位〔范围〕 | 候选完整请求 ms，中位〔范围〕 | 子进程峰值 MiB，基线→候选 |
| --- | ---: | ---: | ---: |
| cross-129 | 8.66〔7.79–17.37〕 | 8.19〔8.14–15.68〕 | 4.20→4.36 |
| idt-129 | 8.39〔8.13–9.61〕 | 8.58〔8.25–9.19〕 | 4.14→4.11 |
| nonlinear_idt-129 | 18.47〔18.14–19.63〕 | 15.65〔15.28–16.39〕 | 4.80→4.83 |
| nonlinear_idt-4097 | 265.18〔261.24–269.55〕 | 168.68〔167.39–174.87〕 | 6.75→7.75 |
| nonlinear_idt-8193 | 538.91〔527.10–569.02〕 | 343.09〔341.14–348.89〕 | 8.92→11.09 |
| pwl-129 | 7.02〔6.91–12.15〕 | 7.02〔6.95–8.46〕 | 3.50→3.50 |
| timer-129 | 9.17〔9.04–9.19〕 | 8.89〔8.83–9.92〕 | 4.34→4.47 |

7 例共 140 次执行，零失败；同例在两核、诊断开关及五轮之间的完整 JSON 逐字节一致。独立解析答案、原电压/事件预算及精确包围另行核验。4097/8193 点非线性请求的耗时范围不重叠，但峰值 RSS 分别增加约 1.0/2.2 MiB，属于缓存换时间的实测代价，不能称为内存优化。memo 未设容量上限，本次有限查询不能证明任意长仿真的内存上界。短请求不作提速承诺。

原始响应、逐轮耗时、诊断及 `time -l` 日志为 local-only，保存在所属工作区 `runs/performance-p03-20261017/review-complete-request/`。收据保留全部样本和输入/输出/内核哈希。主机共享且有外部负载，未删除慢样本；结论不扩展到任意模型或相对 Spectre 的速度。两个 PR 均未合并；源码未改，原代码正确性及 Spectre 复用边界保持。

## 只拆 IR crate

IR 是版本化数据与请求解码边界，不拥有数学误差、求解器或历史。新 `evas-ir` 只使用现有 serde/serde_json，`evas_kernel::ir` 转导出原类型，JSON16 和 `evas_kernel::{ir,solver,run,run_with_threads}` 入口保持兼容。

```mermaid
flowchart LR
  JSON[JSON16] --> IR[evas-ir: 类型与解码]
  IR --> K[evas-kernel]
  K --> S[solver: 矩阵与原关系]
  K --> C[transient Controller: 接受 Frame 与提交]
  C --> O[operators: 调用点历史]
  C --> E[events: 批次与认证]
```

内核仍有 `affine_bounds ↔ event_accuracy`、`operators ↔ continuous`、`events ↔ event_conditions` 和 `events ↔ guard_trajectory` 依赖。现在强拆会扩大公开接口或复制语义。因此数值运行时保留一个 crate，进一步拆分先消除这些具体依赖。类型归 IR；数学误差与数值算法归内核；历史归算子调用点；接受 Frame、事件游标及一次提交归统一 Controller。诊断只观察。

构建在临时源码副本及独立 target 中测 clean、warm、改单个 solver/operator 文件的 check/build/test。test 用 `--no-run`，不是测试执行时间。固定提交各重复两次，结果如下。样本少，warm 检查及极短更新受波动影响；不承诺其他主机或全部构建都变快。

| 构建边界（秒，中位数） | main 6994ada4 | IR b20ff5ec |
| --- | ---: | ---: |
| check / clean | 8.703 | 6.352 |
| build / clean | 10.527 | 9.255 |
| test / clean | 18.662 | 16.102 |
| check / solver | 0.377 | 0.305 |
| build / operators | 1.050 | 0.774 |
| test / operators | 1.337 | 1.181 |

## 输出协议与后续范围

保留完整 JSON 响应。4097 点输出约 0.4–0.5 MB；积分热点在候选准备与历史查询。另测 131073 点斜坡，观察输出和 RSS 增长，不证明任意长瞬态可扩展。分块/二进制协议移交后续 Issue。

后续协议至少要定义运行身份、块序号、预期观察点、成功终止标记及失败/取消尾部。缺少终止标记的部分输出不能作为完整成功。当前 stdio MCP 只查询已生成 session，不提供运行中流式结果。

填充排序/存储见 [#57](https://github.com/BucketSran/vaEVAS/issues/57)，历史查询与动态 guard 分段见 [#58](https://github.com/BucketSran/vaEVAS/issues/58)，长输出协议见 [#59](https://github.com/BucketSran/vaEVAS/issues/59)。当前不放宽容差、不复用旧 Jacobian、不开放事件修改 guard 后重定位。数学见[求解手册](../../evas/docs/math/solving.md)，用户查询见[诊断说明](../../evas/docs/reference/diagnostics.md)。


## 事件窗口电路组装复用

[PR #207](https://github.com/BucketSran/vaEVAS/pull/207) 在单个事件窗口复用电路结构，仍按原 contribution 顺序重算数值。基线 `49f24f0b`，行为候选 `fa291448`，冻结 release 内核及请求身份见[紧凑收据](assembly-plan-reuse.json)。

使用维护中的 `profile_requests.py`，新旧各五轮，逐轮交换先后顺序。正式计时关闭诊断，另跑开启诊断的等量请求核对完整响应和路径计数。边界含 Python 序列化、进程启动、内核读入/解析/求解/编码和 Python 解析，不含 VA 编译、答案检查或归档写盘。macOS `time -l` 记录内核子进程峰值 RSS；表中为五轮最大值，未与 Python 全进程 highwater 相加。

| 案例 | 基线完整请求 ms，中位〔范围〕 | 候选完整请求 ms，中位〔范围〕 | 子进程峰值 MiB，基线→候选 |
| --- | ---: | ---: | ---: |
| cross-8193 | 88.81〔86.93–100.46〕 | 86.52〔85.74–99.27〕 | 8.34→8.45 |
| idt-8193 | 150.78〔148.38–157.11〕 | 141.18〔138.65–143.64〕 | 8.34→8.16 |
| nonlinear_idt-8193 | 532.53〔528.45–547.38〕 | 525.37〔512.97–541.09〕 | 8.89→8.97 |
| pwl-8193 | 47.60〔46.74–47.94〕 | 47.99〔47.49–49.82〕 | 6.38→6.34 |
| pwl_idt-8193 | 206.47〔201.12–209.47〕 | 195.64〔190.87–202.66〕 | 8.91→9.03 |
| timer-8193 | 104.87〔103.75–106.98〕 | 104.22〔99.27–108.61〕 | 8.41→8.52 |

6 例共 120 次执行，零失败；同例在两核、诊断开关及五轮之间的完整 JSON 逐字节一致。独立解析答案、原电压/事件预算及精确包围另行核验。idt/pwl_idt 的收益仅限本表的固定合成负载，其余小差异不作稳定提速结论；旧 nonlinear 噪声样本仍保留。RSS 差异小于约 0.2 MiB，不推断通用内存改善。

原始响应、逐轮耗时、诊断及 `time -l` 日志为 local-only，保存在所属工作区 `runs/performance-p05-20261017/review-complete-request/`。收据保留全部样本和输入/输出/内核哈希。主机共享且有外部负载，未删除慢样本；结论不扩展到任意模型或相对 Spectre 的速度。两个 PR 均未合并；源码未改，原代码正确性及 Spectre 复用边界保持。
