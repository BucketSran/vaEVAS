# 连续历史闭区间索引 F2

端到端性能结论未决。30 次计时请求已经用完，29 次完整成功，最后一次候选在 30 秒上限超时。
真正进入优化路径的请求只得到基线 5/5、候选 4/5 次成功，未满足每边五次完整成功的要求。
外部负载明显变化，不能用成功样本的中位数宣称速度提升。没有重试，也没有从分母移除超时。
当前索引保留为待独立 review 判断收益/成本的候选；F2 的完整性能验收尚未完成。

## 范围与证据

基线为 `d06581f92628ab9e94a2d16bf600b0225174bb6d`。仅修改线性 `range_bounds`、
`derivative_bounds` 的段筛选，两次二分查找后保留同一闭区间相交切片及原 hull 次序。
没有保存查询答案、额外索引数组或新的接受历史。区间传播、DC、异常、单点 lookup、
非线性源遍历与事件调度保持原算法。

[紧凑收据](history-windows-results.json)记录实际二进制、请求与来源哈希、逐次成功时长、
超时分母、独立答案、profile 计数和负载。历史二进制、完整 stdout、diagnostics、
源快照与负载记录留在 ignored `runs/f2/`；它们为本地证据，哈希不代表公开下载。
两份原始收据的 `candidate_revision` 记录的是检出 HEAD d06581f9；候选包含当时未提交的源码改动，
不能读作干净基线。紧凑收据的 `review_corrections` 明示该 dirty 状态、实际源码 SHA 和原收据 SHA。
原始收据不改写，已提交候选的生产前缀与测量快照相同，后续新增的是测试断言。
计时脚本身份以 `executed_joint_tool_sha256` 为准，后加的失败处理不追记为当时已执行。

第一组固定请求使用 `u=t, y=u+idt(u,0)`，8192 段、1025 输出，加上 2 段、129 输出的控制请求。
两边各五次，完整结果逐字节一致。然而 profile 没有 F2 query 计数，证实它经过直接源积分路径，
不能回答本次索引的成本问题。这 20 次计时全部保留，控制请求只作为回归控制。

第二组先做非计时路径 gate，再固定联合反馈 `z'=u-z, z(0)=0, y=u+z`。
独立解是 `y=2t-1+exp(-t)`。8192 段、1025 输出下，原先设在 source knot t=0.5 的 guard
在两边都以相同 `event_resolution` 信息拒绝，失败请求保持原样。
新请求把根设为 t=0.53，阈值为 binary64 常量 `0.6486049696783552`，避开 source knot。
九次成功响应逐字节相同，最大解析电压误差 `1.44e-14`，事件时刻满足 `1e-10` 的独立检查。
第十次候选超时。原测量脚本没有保留该超时的部分流，完整异常保存在收据；脚本现已补上失败 launch
计数和可用部分流的保存，这个工具修正没有产生额外计时。

| 请求 | 基线成功次数/尝试次数 | 候选成功次数/尝试次数 | 基线成功范围 ms | 候选成功范围 ms |
| --- | ---: | ---: | ---: | ---: |
| 原直接源，多段 | 5/5 | 5/5 | 1008.36–2250.11 | 998.12–1701.63 |
| 原普通控制 | 5/5 | 5/5 | 30.57–32.75 | 30.40–32.60 |
| 联合反馈，多段 | 5/5 | 4/5 | 24621.21–25869.72 | 24494.66–25360.70 |

## 工作量与瓶颈

非计时的 2048 段联合反馈 profile 记录真实运行中的筛选工作。两边均执行 6462 次历史查询、
18518 次段求值，完整输出逐字节相同；全遍历检查 13234176 个候选段，索引切片检查 18518 个。
此计数排除二分查找的比较，描述原来的线性遍历工作。二分另需 O(log N) 比较，实际区间求值保持 O(K)。
没有把仪表化二进制的时长纳入生产计时。

8192 段候选 gate 的 profile 中，`controller.prepare_candidate` 占 22.71 秒，
两类 F2 查询合计约 1.96 秒，整个 kernel 为 25.22 秒，嵌套阶段不能相加。
源码显示 `observed_after` 经 `mapped_event`，无变化时仍可能复制整个线性历史；这与大跨度阶段耗时相符，
但这次没有独立计量其复制字节或直接 clone 耗时，具体归因仍是源码推断。
F2 不改候选复制。即使筛选工作大幅减少，也不能推导同量级的端到端提速。

代价是一个私有切片 helper，每次区间查询两次二分，零额外历史存储。
[连续数学说明](../../evas/docs/math/continuous.md#线性解析传播)给出排序和闭区间等价证明。
是否保留该实现由独立 review 检查这份实际工作量、边界证据和未决性能结果；本记录不宣称性能验收完成。

## 正确性和复现

Rust 最终 149 passed、1 existing ignored；Python 95 passed，覆盖 continuous dynamics、dynamic closure、
dynamic cross、event-window sampling、lifecycle closure、semantic invariants。
其中保留真实同引擎拒绝后重试与 accepted frame 回滚义务；这些结论来自测试执行，不能由重新启动进程替代。
测量 checker 的 3 个校准测试接受独立参考值，拒绝错误电压、错误根、缺失输出和错误时间网格。
补强时间网格检查后重分析全部 29 个完整计时响应，均通过，原超时结论保留。

独立 Rust fixture 检查 `y=u+idt(u,0)` 在 `[1,1]` 的导数同时包含 0、2，以及多断点、DC、stop、
非零历史起点、退化终点、无覆盖/非法窗口与只读查询。原完整遍历只作次级等价 oracle。

请求工具 `history_windows.py prepare` 可重建冻结成功请求。`--case initial` 默认 20 次计时，
`--case joint-history-offset` 另用 10 次计时；一次研究应合计预算，不能重新启动脚本规避上限。
两边使用 `cargo build --release --locked`，相同绝对预算 `1e-8`、相对预算 0、单线程和 max_step `1/1024`。
边界包括 spawn、内核读取/解析/求解/编码、Python 响应解析；请求编码、归档、答案检查和诊断解析在边界外。

```sh
PYTHONPATH=evas/src python3 -B experiments/performance/history_windows.py prepare --requests runs/f2-new/requests
python3 -B experiments/performance/history_windows.py measure --case joint-history-offset --requests runs/f2-new/requests --out runs/f2-new/paired --baseline /absolute/baseline-kernel --candidate /absolute/candidate-kernel --base-revision BASE_SHA --outside-contention 'OBSERVED_LOAD_AND_COMPETING_WORK'
```

`history_windows_profile.py` 从指定源码生成独立 profile 副本，基线默认全遍历，候选加 `--indexed`。
在临时 checkout 构建该副本；禁止把 profile 二进制当生产时长。
所有新计时都需要新的资源授权和 quiet interval；本轮预算已经耗尽。
本结果只覆盖 #58 的区间筛选候选，候选共享与更广的 guard horizon 工作仍未完成。
