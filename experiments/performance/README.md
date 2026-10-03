# 求解成本与内核边界

本目录测量静态求解、瞬态推进及构建成本。测量用于选择优化；不增加原 31 条件的分母，也不证明相对 Spectre 更快。

## 本轮结果

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

阶段包含子阶段，不能相加。输出点、候选次数与积分器内部步数分开记录。历史复制只统计调用次数与逻辑算子槽数，尚无分配/复制字节计数。短请求受进程启动和计时波动影响；诊断有额外成本。这些结果仅适用于固定合成工作负载。

## 重跑

先在收据指定的两个提交分别构建 release 内核。测量时不要同时构建或运行测试。从仓库根目录运行，输出目录必须不存在：

```sh
mkdir -p runs/performance/requests
EVAS_BENCH_REQUESTS="$PWD/runs/performance/requests" cargo bench --locked --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_REQUESTS="$PWD/runs/performance/requests" cargo bench --locked --manifest-path evas/rust_core/Cargo.toml --bench transient_solver
python3 -B experiments/performance/profile_requests.py --kernel /absolute/candidate/evas-kernel --baseline-kernel /absolute/baseline/evas-kernel --baseline-revision BASE_SHA --requests runs/performance/requests --out runs/performance/paired --repeats 5
python3 -B experiments/performance/measure_build.py --output runs/performance/build --repeats 2
```

20 个静态用例覆盖链、环、星、网格、固定种子网络、稠密与多项式。答案来自递推、构造的精确根或独立二分。五个瞬态用例检查斜坡、解析积分、`1/(1+t)` 及手算事件时刻。额外长斜坡由同一 PWL 请求将 `output_times` 改为 `[i/131072 for i in range(131073)]`。

完整边界为 Python 序列化 → 启动进程 → 内核读/解析/求解/编码 → Python 解析。不包含 VA 编译、磁盘归档、答案检查或诊断 sidecar 解析。macOS 用 `time -l` 测内核子进程峰值 RSS；Python highwater 是整个测量进程截至该次的峰值，含先前用例。两者不能相加当作同时峰值。其他平台缺少指标时为 null。

原始请求/stdout/日志/sidecar 保存在本地 ignored 归档。GitHub 保存摘要与重跑工具；哈希不代替可下载的原始材料。收据区分基准提交与实际源码哈希，不把未提交树称为该提交。

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

构建在临时源码副本及独立 target 中测 clean、warm、改单个 solver/operator 文件的 check/build/test。test 用 `--no-run`，不是测试执行时间。两次重复只支持局部 check/build 改进；clean test 波动较大，不承诺全部构建变快。

## 输出协议与后续范围

保留完整 JSON 响应。4097 点输出约 0.4–0.5 MB；积分热点在候选准备与历史查询。另测 131073 点斜坡，观察输出和 RSS 增长，不证明任意长瞬态可扩展。分块/二进制协议移交后续 Issue。

后续协议至少要定义运行身份、块序号、预期观察点、成功终止标记及失败/取消尾部。缺少终止标记的部分输出不能作为完整成功。当前 stdio MCP 只查询已生成 session，不提供运行中流式结果。

填充排序/存储、历史查询与动态 guard 分段、长输出协议分别跟踪。当前不放宽容差、不复用旧 Jacobian、不开放事件修改 guard 后重定位。数学见[求解手册](../../evas/docs/math/solving.md)，用户查询见[诊断说明](../../evas/docs/diagnostics.md)。
