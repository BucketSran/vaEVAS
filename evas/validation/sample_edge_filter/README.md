# 采样、保持、边沿与一阶滤波

本组是工程组合开发验证，补充既有 27 条件，不改写它们的输入、判据或历史结论。
目标是验证同一份 VA 在 EVAS 与 Spectre 中的采样值、次数、边沿和滤波状态。
它不授予原核心集的精确边界资格，也不是未参与开发的论文确认集。

## 固定输入与判据

[contract.py](contract.py)保存四类模型、刺激、手算事件及独立答案。
时间单位为 1 µs，停止时刻 8.5 µs，避开 timer 的停止端点争议。
全部采用明确的非零常数初态，输入在初始时刻与其一致。
任意实数输入表达式的 `initial_step` 赋值不在本轮准入范围。

| 条件 | 主要义务 |
| --- | --- |
| SEF-TIMER | 每 2 µs 采样，保持值经过固定延迟和不同上、下沿，再进入低通 |
| SEF-RESET | 时钟上升沿与复位上升沿共享事件体；复位期间保持初值，滤波历史连续 |
| SEF-INTERRUPT | 每 1 µs 改目标，打断尚未完成的上、下沿 |
| SEF-ISOLATION | 两实例使用不同采样相位、周期、边沿、滤波时间常数和采样增益 |

共同允许误差在执行前固定：输出 100 µV、输入 10 nV、事件观测窗口 ±5 ps。
事件计数为精确整数，要求单调、不能跳过事件，最终次数与手算一致。
原生计数变化的相邻记录须都位于对应窗口，保持值必须与该计数指向的采样一致。
边沿与滤波在全部记录上与名义解析答案比较，不排除边沿窗口。
每次比较保留实际记录时间，不插值或以邻近行替换所需记录。
起点必须为零，尾点与 stop 的差不超过 5 ps，全局记录间隔不超过 1/16 µs。
这是一组有限观测要求，不等同于完整时间域误差上界或隐藏回调时刻证明。

Spectre 三档使用相同模型、刺激与 strobe 请求：基础 `reltol=1e-5`、
`vabstol=1e-7 V`、`maxstep=1/64 µs`；第二档只收紧为 `1e-9/1e-11 V`；
第三档再把步长缩为 `1/256 µs`。固定 `traponly`，保留全部档位结果。
EVAS 使用 `vabstol=1e-7 V, reltol=0`，另核对稀疏/密集查询的共同点逐位一致。
两端内部设置不声称等价。

## 工程验收与严格边界诊断

2026-10-10 用户接受 [SEF-TIMER-18](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#accepted-timer-18)
为本批已知差异。上述固定判据、全部观察点和预算不变；`contract.py` 不改。
工程通过与严格同刻计数一致分别报告，后者保留原 18 条失败，不再单独阻塞本批工程验收。
这是对已解释观测的接受决定，不是删除事件窗内记录，也不是把同一规则自动用于其他模型。

窗口内仍须核对次数、顺序、采样值及后续边沿/滤波误差。
新增漏事件、超预算、错误历史或普通查询改变结果时重新调查。
原来的输入表达式初态、stop 恰为 timer 的失败探针及任意重叠窗口没有获豁免。
通用分类见[验收标准](../../../docs/contributing/validation.md#classify-differences-before-selecting-a-repair)。

## 独立答案

保持值来自输入 PWL 在名义事件时刻的有理数求值，复位逻辑独立执行。
`transition` 的多边形按已记录的语言/手册规则构造：同向中断保留原起点，反向使用旧目标。
规则出处见[算子手册](../../docs/math/operators.md#transition)。

对于 `τ f' + f = e`，若边沿在 `a` 时刻发生斜率变化 `Δm`，滤波输出增加
`Δm * ((t-a) - τ * (1-exp(-(t-a)/τ)))`，仅对 `t≥a` 生效。
总输出为 DC 初值加全部斜率变化的响应。这与内核逐段状态传播的实现独立。

[校准测试](test_contract.py)包含手算 ramp 锚点，并拒绝漏事件、把滤波器错误重置为输入、
错误输入、非有限数、缺失尾部和重复时间。运行：

```sh
python3 -B -m unittest discover -s evas/validation/sample_edge_filter -v
```

运行入口和实际证据见[对照报告](../../../experiments/backends/sample-edge-filter/README.md)。

## 定向生命周期回归

以下三项回归已由 [#193](https://github.com/BucketSran/vaEVAS/pull/193) 合入；本节补充其独立验收范围。

[公开链路测试](../../tests/test_sample_edge_filter.py)另用手算数值检查两个容易混淆的时段。
它们复用上述 VA 和刺激，独立写出局部解析答案，不调用 `segments` 或 `filter_value` 生成预期值。

| 回归 | 要区分的行为 |
| --- | --- |
| `test_reversal_keeps_old_edge_until_delayed_activation` | SEF-INTERRUPT 在 2 µs 采到 0.1 V，旧边沿仍以 +1/3 V/µs 上升到 2.125 µs，此后才按 −0.52 V/µs 反向；滤波器继续积分这段旧边沿 |
| `test_hold_reset_retains_filter_history_through_delayed_fall` | SEF-RESET 在 2.25 µs 将保持值复位为 0.25 V，边沿在 2.375 µs 才下降；滤波输出从原有非零状态续算，不能重置为保持值或当前边沿值 |

两项都比较跨过整个关注区间的稀疏查询、局部查询和加密查询，并核对共同点及事件记录一致。
局部边沿和滤波答案使用 1 nV 的 EVAS 回归容差；这不替换上文 Spectre 工程比较的 100 µV 预算。

候选状态另由 [Rust 控制器回归](../../rust_core/src/transient_lifecycle_tests.rs)
`reset_closure_retries_q_and_nonzero_count_from_the_accepted_frame` 检查。
它在同一控制器中重复准备、丢弃候选，再经历精度拒绝和重试。
复位使积分输出从事件前的 2 变为 1，同刻重算必须令 `q=1`，而计数只从 7 增为 8。
第二个事件再增为 9。该测试补充已有普通计数重试测试，不声称覆盖全部事务失败路径。

这些是开发回归，不扩大支持范围或同源码兼容资格。运行：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
cargo test --locked --manifest-path evas/rust_core/Cargo.toml reset_closure_retries_q_and_nonzero_count_from_the_accepted_frame
PYTHONPATH=evas/src:evas/tests python3 -B -m unittest -v test_sample_edge_filter
```
