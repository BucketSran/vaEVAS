# 来源与验证边界

本题由本仓库的积分历史重定位实验提出，不包含第三方模型源码。
候选身份为 [BC-0001](../../CANDIDATES.md#bc-0001)；这里是已校准的原型，尚未正式纳入 benchmark。
问题来源是双向 cross 的事件体改变自身积分斜率，返回穿越再次触发。
题目评估模型是否稳健表达指定振荡行为，不把某个仿真器的波形当作唯一数学答案。

参考解使用上限向上、下限向下的有向 cross；其他满足规格的写法同样可得分。
检查器从正速度输入的分段积分与三角波折返关系推导答案。
本题单独校准，不加入已完成的六题初筛分母，也不改变 EVAS 原 31 条件矩阵。

评分源码为 [triangle_oscillator.py](../../checkers/triangle_oscillator.py)，
`tests/triangle_oscillator.py` 是逐字节相同的 canonical 副本。
`tests/verify.py` 经公共 `circuit_task` 执行边界调用 `first_batch_triangle` 薄适配层，
仍使用原 `triangle_oscillator.evaluate` 独立判据。配置生成、校准与后端差异证据见
[振荡器兼容性实验](../../../experiments/backends/dvs2-spectre-validation/README.md#oscillator-compatibility)。
任务需要已配置许可证的 Spectre verifier；Docker 基础镜像不包含 Spectre。

在已配置 Spectre 的环境可运行 `tests/test.sh`；用 `CANDIDATE` 和 `VERIFY_OUTPUT`
指定源码与全新输出目录。基础设施错误不产生模型分数。

<a id="local-evas"></a>

## 通过 harness 调用本地 EVAS

[triangle_evas.py](../../checkers/triangle_evas.py) 是本题的本地开发验收入口。
它准备任务输入并调用原独立检查器，circuit harness 负责执行和证据回收。
当前只接受 `constant-tighter`；不写 Harbor reward，也不替换 `tests/verify.py`。

从 vaEVAS 根目录构建内核，然后显式指定两个 checkout、候选与全新输出目录：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
python3 -B benchmark/checkers/triangle_evas.py \
  --harness-checkout /path/to/circuits/harness \
  --evas-checkout /path/to/vaEVAS/current \
  --kernel /path/to/vaEVAS/current/evas/rust_core/target/debug/evas-kernel \
  --candidate benchmark/tasks/va07-triangle-repair/solution/dut.va \
  --case constant-tighter --output runs/va07-evas-new \
  --timeout-s 60 --max-output-bytes 16777216
```

harness checkout 需要包含 `alphaapollo/common/execution/chips/current_evas.py`。
普通主 checkout 不一定含该未发布接口；执行前核对实际路径与源码身份，不能只根据目录名推定可用。
首次执行前保留构建命令、输出与 Rust/Cargo 版本。程序分别给原网格和补充网格
60 秒执行预算；前一轮执行故障时停止，整题不会被记为模型失败。
退出码 `0` 为本配置开发验收通过，`1` 为独立判据检出的模型失败，`2` 为执行故障或未决。
所有结果的 `benchmark_score` 都为 null。

| 设置 | 原 Spectre 配置 | 本地 EVAS 请求 |
| --- | --- | --- |
| `vabstol` | `1e-14` | `1e-8` |
| `reltol` | `1e-12` | `0` |
| `iabstol` | `1e-18` | 无对应 transient 参数，明确记录未映射 |
| `method` | `traponly` | 无对应 transient 参数，明确记录未映射 |
| 模型参数、`ttol/vtol`、激励、stop、maxstep | `tests/cases.json` | 保持原值 |

映射沿用已有 `oscillator_compatibility.py` 的 EVAS 条件，不逐候选调整。
收据保存完整源配置、实际 manifest、映射依据、不支持项和源码快照。
哈希标识的 EVAS CLI/runtime 转发这组请求，但内核没有独立回显全部生效容差。
同名字段不能视为两种求解器的误差保证等价。

原 601 点网格必须单独执行并保留。该网格最大间隔为 5 ms，不能直接提供 200 ns 的
换向时间证据。第二轮保留原网格全部点，并在独立解析根前后各加 `time_atol/2`，共 607 点。
这明确增加了观察查询，不改变模型、激励、求解容差、最大步长和外部判据。
两个候选使用相同的预定查询，禁止从引擎自报事件时间生成采样点。

两轮都调用原 `evaluate(rows, case)` 并保留完整输出，不传可选的 `event_times`。
波形及计数合同需分别通过，共同采样点的波形还需在 `wave_atol` 内一致。
时间验收检查补充网格中每次计数变化的前后采样区间，只有整个区间都在原 `time_atol` 内才通过。
若根前补充点已经变化、前一个旧计数点却很远，则返回未决；这些样本无法区分
合法的提前 150 ns 与超差的提前 1 µs，不能只凭首次新计数点通过，也不能直接记模型失败。
延迟侧同样处理：合法的延迟 150 ns 与超差的延迟 1 µs 会得到相同的采样计数，
首次新计数点均在根后 5 ms。原 checker 的逐点时间判断保留为失败，但开发验收记为未决；
波形或计数合同已经证明的错误仍记为失败。
原始 JSON 中的自报事件另作诊断，不能补足或替换独立波形证据。
这是两个指定网格的开发验收，不是连续时间认证或一般查询网格不变性证明。
两轮源码、内核、Python 和环境设置必须一致；适配器与 checker 加载后发生源码漂移也拒绝评分。
适配器直接编译 canonical checker 的源码字节，避免复用此前缓存的旧 checker。

无需仿真器的适配回归与跨仓缺内核检查：

```sh
HARNESS_CHECKOUT=/path/to/circuits/harness \
  python3 -B -m unittest discover -s benchmark/checkers -p test_triangle_evas.py -v
```

2026-10-05 的实际本地执行使用 vaEVAS `e19a1ba7` 的内核源码和本地适配改动，
harness 基于 `c292140d` 的本地改动；两边均未发布本次接入。
内核为 `evas-events-0.13.0`，SHA-256 为
`0302cf06db0f440a07b763713e89b0d24d545ef5a077cbffa22daf662609d028`。
参考模型补充网格的最大波形误差约 `4.55e-13 V`，最大换向时间误差约 `1.00e-7 s`，
恰好 3 次换向，共同网格电压差为 0。原网格自身的时间判据未通过，不能隐藏这一结果。

同配置的既有 wrong-speed 变体将积分速度乘以 `0.5`。真实 EVAS 执行返回
`kernel.event_resolution: cannot determine dynamic cross sign at interval end`，没有完整波形。
因此真实负例的独立判据验收仍未完成；构造波形被正确检出不替代这项实测。
这是独立的引擎数值拒绝/支持范围缺口，尚未证明具体算法缺陷。本接入不修改内核或放宽判据。
诊断中将 stop 改为 2.99 s 能取得一次换向，改为 3.125 s 并相应延长恒定激励能取得两次换向。
这支持拒绝与停止端点相关的假设；这些改条件的运行只用于定位，不计入原配置验收。
原运行及构建收据保存在 harness 的本地 `runs/chips/validation/20261005-local-evas/`，
其中初次 `reference/report.json` 与 `wrong-speed/report.json` 保留原结果，
审查修复后的重跑保存在 `final/` 和 `final-v2/` 下的同名目录；`final-v2/`
包含最后的依赖缓存修复，记录输入、源码和产物摘要。
这些原始材料为 local-only，不是公开下载数据；本次没有执行 Spectre、SSH 或模型实验。

## 首批公共执行入口迁移

Harbor入口只更换执行边界：候选约束、实际Spectre版本、求解、归档和收据由
首批公共`circuit_task`负责。适配层原样调用canonical独立数学答案，
只将其`BehavioralRejection`转为完整波形的有效失败；结构和数据错误继续保持checker错误。
参考VA、原八例cases的完整字节、刺激网表、参数、1 uV/200 ns容差和次数要求不变。
`contract.json`额外声明观察信号`ctl,z,count`，均是原网表直接保存的节点：
r接地，ctl是正速度输入，z是三角波输出，count是换向次数电压。
公共执行器读取该默认映射，不把metadata写入原cases文件。
这保留旧EVAS replay的冻结case身份；canonical数学、旧runner和EVAS支持结论不变。

`experiments/benchmark_first_batch/legacy_va07/prepare_candidates.py`仅调用原
`oscillator_compatibility.experiments`构造参考和四个历史负例，未改变其语义。
一份等价product-guard源码另配两次历史刺激，不能称为两份不同等价实现。
旧题真实Spectre校准仍是历史身份；首批新入口的8参考条件、4定向负例
与可选2等价条件由协调者重新冻结和运行，迁移本身不证明后端已通过。

<!-- generated first-batch metadata -->
- `engineering_action`: `diagnosis-repair`
- `source_group`: `repository-triangle-oscillator`
- `context_level`: `bounded-work-unit`
- `provenance`: `development-regression`
- `data_provenance`: `not-applicable`
<!-- end generated first-batch metadata -->
