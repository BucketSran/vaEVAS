# EVAS

当前实现为 **EVAS 0.7.0，IR v7**：静态多项式求解，以及限定 PWL/仿射网络的 `cross` 和固定参数 `timer` 事件执行、离散状态驱动的 `transition` 波形及直接 PWL 输入的 `absdelay` / `slew`，以及显式常量初值的受限 `idt`。尚未替换旧 EVAS 0.8.7。

0.5.3 恢复同块 integer 顺序重复赋值，保留逐句范围检查、同刻前向误差认证与原子提交。
当前回归与对照见 [0.5.3 证据](../experiments/dvs2-spectre-validation/README.md#pr12-integer-sequence-053)；
特定 Spectre 版本的异常单独由 [Issue #16](https://github.com/BucketSran/vaEVAS/issues/16) 跟踪。

从限定的 Verilog-A 源码生成贡献方程，再由 Rust 同时求解节点电压，允许自反馈与实例间反馈。
`solve` 的每个样本独立求静态工作点；`transient` 沿物理时间推进，保存实例私有状态。两种入口明确区分。

长期范围是声明的电压域行为及交互，与 Spectre 对标，并为 VABench 的开放复现及
agentic eval 提供后端。当前支持由语法和语义决定，运行时不识别验证集或模型名称。

[技术手册](docs/README.md)提供数学/执行说明；[能力与缺口总表](docs/CAPABILITIES.md)区分 main、开发分支和证据状态。

## 构建与运行

需要 Python 3.10+ 和 Rust/Cargo。以下命令在仓库根目录运行：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas compile evas/examples/static_sum.json
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_sum.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_nonlinear.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m evas transient evas/examples/cross_counter.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m evas transient evas/examples/timer_counter.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m evas transient evas/examples/idt.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
cargo test --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 evas/tests/run_static_regression.py --kernel evas/rust_core/target/debug/evas-kernel --output runs/evas-static-replay
```

回放命令要求新的输出目录，读取原 31 条件的 VA、输入和独立判据。
当前静态回放接受其中 11 条（V2 四条、V7 线性三条、V7 非线性两条、S1 两条），其余 20 条明确拒绝。
两档对应 4,001／40,001 点的静态采样网格和电压/残差容差，不是瞬态仿真或 DVS 正式资格。

## 回归证据

0.7.0 / IR v7 在 PR18 基线 `1dc0bed` 上整合受限 idt，完整检查为 **218 项 Python、42 项 Rust**，
另有 **9 项纯数学校准**；locked/offline 构建、all-targets warnings-as-errors 与格式检查通过。
新增的两项 Rust 检查覆盖非零已接受历史、四调用点/两实例、真实精度失败后较早候选重试，
以及只修正未来输入的同刻重算。数学、状态生命周期和剩余证据边界见
[积分契约](validation/DYNAMICS_CONTRACTS.md)及[实现说明](docs/OPERATORS.md#idt)。
本次没有新增 Spectre 对照或重跑原 31 条件矩阵；下述矩阵数字仍属于原检查点，不能当作 0.7.0 新执行结果。

PR15 被测实现 `e01fb5b` 包含 PR14 `3638024`，继承 PR13 0.6.1 的历史误差验收；该检查点 **195 项 Python、33 项 Rust**、locked/offline 构建、warnings-as-errors、格式与 CLI 检查通过。父提交 `9850450` 的检查为 **155 项 Python unittest 方法、23 项 Rust 测试**，以及锁定依赖的
离线构建、warnings-as-errors 的 all-targets 检查和格式检查。新增历史误差认证见[算子手册](docs/OPERATORS.md#历史误差与电压精度)。PR13 0.6.1 与历史执行收据见 [PR13 对照](../experiments/dvs2-spectre-validation/README.md#pr13-transition-061)。
合并收尾只更新文档和实验资产，运行时代码、测试与独立验证定义和被测检查点一致。
新内核瞬态的原 31 条件两档各 13 条达标、18 条明确拒绝，详情与 absdelay/slew 专项见[本轮实验](../experiments/pr14-pr15-validation/RESULTS.md)。
下面各阶段的计数和静态回放属于各自历史版本，不与本轮数字相加。
其中 26 项 Python 方法覆盖事件时间/方向/次数、时移/斜率/步长变化、初始化、
内部节点触发、实例隔离、同时事件、孤立触零、零平台/停止点、容差别名及拒绝边界；3 项 Rust 测试覆盖
丢弃候选后重试、事件后残差失败和整数溢出时状态不提交。它们不是跨后端资格测试。

0.4.3 的原 11 条件 × 两档 = 22 组，共 **484,022 个静态点**满足原独立判据；
0.4.3 启用 JSON 的 binary64 往返精度；22 份波形与 0.4.2 均有末位变化，
最大差异约 `4.44e-16 V`，不再宣称逐字节一致。其余 20 条拒绝诊断及验证材料保持不变。
新增无 `transition` 的计数器示例产生约 0.5、1.5、2.5 µs 的三次事件，最终状态为
上升沿 2 次、下降沿 1 次。这些开发探针不替换原 E1，也不改变原 31 条件的分母或支持数量。

精度回归的 10 项 Python 方法覆盖方程缩放、独立高精度参考、容差细化、电压量级、耦合、
矛盾约束、数值秩不足、停滞与容差接口；Rust 增加小残差及其导数的手算对照。
本轮继承 4 项 Python 方法和 4 项 Rust 测试，覆盖分解复用、多 RHS、行缩放、主元、冗余约束及零未知量。
另有 1 项瞬态入口回归检查新旧容差名称的事件轨迹一致，并拒绝歧义参数。
0.4.3 新增 11 项事件精度/数值传输测试，以 Python `Fraction` 独立检查浅斜率、
耦合网络、上升/下降方向、大时间偏移、不可表示容差、同刻/邻近事件和拒绝边界。
另有 1 项独立算术测试：4,102 对数值的加减乘除，共 16,408 个结果，均包含对应的精确有理数答案；
包含随机 binary64 指数、相消、下溢和溢出。测试临时编译 Rust 算术探针，需要 `rustc`。
新增 2 项 Rust 测试检查精确乘积比较、相消、下溢及除零边界。
0.4.4 另有 2 项 Python 方法（6 个反例）和 1 项 Rust 测试，检查系数相消/下溢不能掩盖
状态与电压乘积；覆盖 VA、原始 IR、guard、贡献、赋值以及无事件瞬态入口。
`y=y-s*(y+y^3-1)` 在 `s=1e-13` 时曾错误返回 0；本轮返回约
`0.6823278038283471`，与独立参考的误差约 `3.28e-13 V`。

程序测试方法数与独立验证条件数分开报告。本轮新增控制属于 EVAS 开发回归，
没有增加原 31 条件的跨后端分母，也不称为未见确认集。
旧检查点的执行身份与 review 记录见
[历史记录](https://github.com/BucketSran/vaEVAS/blob/b877e5b/evas/REVIEW.md)，
初始内核审查见已合并的 [PR #2](https://github.com/BucketSran/vaEVAS/pull/2)；后续阶段的范围、验证摘要与证据哈希记录在各自提交和 PR 中。
本轮未重跑原 31 条件四后端矩阵；0.4.6 未改静态求解路径，静态回放数字继承 0.4.3。
事件对照使用独立的小条件，仍未取得完整瞬态资格、通用非线性收敛或跨仿真器性能优势结论。

0.4.4 的历史 [Spectre 对照](../experiments/dvs2-spectre-validation/README.md#pr7-cross-小规模对照)
包含 8 条件 × 两档：EVAS 满足当前有限观测判据 16/16，thu-sui 的 Spectre 为 14/16。
差异集中在同侧触零：旧 EVAS 忽略该事件，Spectre 两档都在到达零时触发一次。
这是旧判据与 Spectre 行为的分歧，不能将通过数量解释为精度排名；历史判据和收据保留。

0.4.5 将内部 PWL 孤立零点改为按到达方向触发一次，离开不重复触发。
新增 3 项 Python 方法并修订原节点测试，覆盖四种符号组合、方向、粗细步长、事件后状态、
重复触零、仅差一个 binary64 可表示值时不误触发，以及小幅真实穿越不被容差过滤。
新增测试在旧内核上有 10 个失败项（含子测试），修改后全部通过。
[12 配置回放](../experiments/dvs2-spectre-validation/README.md#孤立触零契约回放045)
新执行 EVAS、复用 thu-sui Spectre 波形，二者各自 144 条普通控制历史、72 条触零历史
满足同一新契约，次数和方向一致；检查器目录共 21 项校准方法通过。
这只覆盖所测显式 PWL 节点，不推广到光滑极值、零平台或停止时刻触零，不改变原 31 条件分母。

0.4.6 将到达规则扩展到零平台入口及 stop：非零到精确零触发一次，零平台停留、离开、
初始零平台与恒零输入不触发；再次离零后重新到零可再触发。终点事件先提交再输出最终状态。
原拒绝测试替换为 5 项回归方法，覆盖方向、极性、粗细步长、20 ps 短平台、重复平台、
近零非零值、停止点之后的输入延伸及终点同刻快照；旧内核上有 99 个错误项（含子测试），
新内核全部通过。[独立边界实验](../experiments/dvs2-spectre-validation/README.md#零平台和停止点边界046)
在 thu-sui 新执行 6 次 Spectre，EVAS 新执行相同 6 个配置；每个后端的 270 条边界历史
和 108 条对照历史满足冻结的到达候选规则。首批 6 次 Spectre 探针编译失败单独保留，
不计为仿真通过。检查器目录共 25 项校准方法通过；这些仍是有限开发证据，未增加原 31 条件分母。

0.5.0 新增 17 项 Python timer 方法和 1 项 Rust 批次回退测试：固定周期/单次、禁用、
参数绑定、实例隔离、t=0/stop、与 cross 同刻及邻近、输出网格/步长变化、原始 IR 拒绝、
整数溢出及事件后残差失败。精确 Fraction 对照包含 2,000 次普通周期和绝对时间 `2^40` 秒
附近的 1,000 次周期，逐项验证 `start+k*period` 的时间误差；不外推任意时长的稳定性。
初始化先安装 initial_step，再执行 timer(0)，stop 上名义事件先执行再输出，属于本版本
明确的 EVAS 约定，不据此要求其他后端在边界容差窗口内产生相同可观测次数。
0.5.0 重新执行原静态回归：11 条件 × 两档 = 22 组、484,022 个点均满足原判据，
其余 20 条仍明确拒绝；此回放验证 IR 迁移后的静态兼容性，不能证明 timer 语义。
上述本地检查点当时未执行 Spectre。后续 [PR12 专项对照](../experiments/dvs2-spectre-validation/README.md#pr12-fixed-timer-comparison)
已在 thu-sui 新执行 24 次 Spectre，并以相同共同模型请求本地 EVAS：选定的 64 条 timer 历史
与 16 个非同刻交互探针，两端均满足独立有限观察判据。但同刻 timer/timer 读取时，
EVAS 得到旧电压状态 0，Spectre 得到新状态 1；隔离的同刻 timer/cross 在 EVAS 上被
事件次序认证拒绝，在 Spectre 上可执行。粗细步长与声明顺序变化下差异仍存在。
这些是 0.5.0 检查点的兼容性缺口；0.5.1 修复与新证据见下文，历史收据保持不变。
上述旧结果未授予 timer 完整跨后端资格；
原 31 条件及支持数量不变。

0.5.1 修复可表示 PWL 根的同刻认证，并将同刻仿射事件更新代入电压方程联立求解。
新增 2 项 timer 根定位/邻近事件回归、6 项同刻求解回归与 1 项 Rust 零点证书测试；
原先断言旧电压快照的四项测试改为明确的新契约。旧内核在两个根定位测试及五个
同刻求解测试方法中失败。新版本同时检查多级级联、实例/语句顺序、正负及非收缩反馈、
整数只更新一次、局部赋值顺序、未触发状态保持，以及非唯一或无解反馈的拒绝。
此版本仍仅支持原有连续 PWL/仿射及状态独立 guard，未引入通用非线性事件迭代。

[0.5.1 修复对照](../experiments/dvs2-spectre-validation/README.md#pr12-timer-repair-051)
完成 30 个 EVAS 配置：原 24 个全部可执行，新增六个级联/反馈诊断也完成。
对应 Spectre 本轮新执行 18 次，另 12 个配置复用经哈希及输入核验的历史波形。
64 条 timer 历史和 16 个邻近交互仍满足原判据；八个同刻探针两端都读到新状态 1；
新增 20 条历史两端都符合独立的联立候选值。旧版拒绝与旧状态读取结果完整保留，
不据此宣称通用同刻语义或整个 Verilog-A 与 Spectre 一致。


PR13 原始 0.5.1 检查点（未合入 main）新增 15 项 Python transition 方法和 4 项 Rust 算子/事务测试，覆盖独立 TR 边沿、
反向/延长/重复/相等目标、下降反射、待生效窄脉冲、双调用点/双实例、timer(0)、
同刻目标、网格变化、失败后队列重试、原始 IR 和跨实例依赖拒绝。
另检查大绝对时间的分辨率失败、相邻未决期限拒绝及临近终点严格不越过目标。
这些是本地开发检查；未执行 Spectre，也未新增或重定原 31 条件的资格/通过数量。
该历史检查点的静态回放重新验证 22 组、484,022 点；原 31 条件中其余 20 条仍留在拒绝分母，
其中 15 条在解析/编译阶段拒绝，5 条新可编译的动态模型由静态入口明确拒绝。
原 D2-V5-01 已有显式 timer 容差，但此处没有执行该条件的瞬态验收，不据编译成功宣布通过。
旧静态驱动首次在第 9 组遇到新可编译动态模型后停止；保留该失败目录，增加分析类型预检后用新目录完成回放。


## 模块与接口

| 模块 | 当前文件 | 唯一职责 |
| --- | --- | --- |
| 语法解析 | `src/evas/syntax.py` | 完整消费 token，生成带源码位置的语法树 |
| 语义绑定 | `src/evas/frontend.py` | 绑定参数、实例与节点，建立贡献支路身份 |
| 表达式转换 | `src/evas/lowering.py` | 常量折叠，生成仿射叶子与多项式表达式 |
| IR | `src/evas/ir.py`、`rust_core/src/ir.rs` | Python/Rust 之间带版本和源码位置的数据契约 |
| 方程组装 | `rust_core/src/assembly.rs` | 校验 IR 与驱动配置，累加支路贡献，生成方程系数及节点分区 |
| 工作点求解 | `rust_core/src/solver.rs` | 代入每个样本的驱动值，求解未知电压，验收原方程残差 |
| 表达式求值 | `rust_core/src/expression.rs` | 递归校验 IR，计算多项式值与链式法则导数 |
| 非线性求解 | `rust_core/src/nonlinear.rs` | 对同一组支路方程执行有界阻尼 Newton 迭代 |
| 线性代数 | `rust_core/src/linear.rs` | 行缩放、选主元、稠密分解与多 RHS 求解 |
| 事件语义 | `rust_core/src/events.rs` | 校验状态/事件身份及依赖，将状态代入方程，准备事件块的状态更新 |
| 事件误差界 | `rust_core/src/event_accuracy.rs` | 从原 IR 包围仿射网络的传递系数，复核状态独立性及冗余约束 |
| 区间算术 | `rust_core/src/interval.rs` | 向外舍入的 binary64 四则运算及精确乘积比较 |
| 连续输入与根 | `rust_core/src/pwl.rs` | 校验连续 PWL、求值、识别方向及区间内孤立根 |
| 同刻求解 | `rust_core/src/settlement.rs` | 联立仿射事件更新与电压方程，重放原赋值并校验一致性 |
| 同刻误差认证 | `rust_core/src/settlement_bounds.rs` | 从原 IR 独立包围事件后解，检查电压与状态各自误差预算 |
| 仿射区间运算 | `rust_core/src/affine_bounds.rs` | 定位与同刻认证共用的向外舍入转换和消元 |
| 事件日程 | `rust_core/src/schedule.rs` | 生成 cross/timer 统一日程，验证定位误差、同刻关系、次序与事件预算 |
| 波形算子 | `rust_core/src/operators.rs`、`transition.rs`、`absdelay.rs`、`slew.rs`、`idt.rs` | 校验独立调用点/输入，保存延迟目标队列、边沿、限速与积分轨迹，提供语义断点与输出值 |
| 时间推进 | `rust_core/src/transient.rs` | 候选试算、原子提交、输出实际接受的事件记录 |
| 进程接口 | `src/evas/runtime.py`、Rust `main.rs` | 一个批次一次 JSON 请求，无 Python 求值回调 |
| 用户入口 | `src/evas/__main__.py` | 读取显式平面电路 manifest，输出 IR 或结果 |

Python 的公开接口：`compile_sources(sources, instances) -> Program`，
`solve(program, driven, samples, kernel=...) -> result`，以及
`transient(program, sources, output_times, stop=..., max_step=..., kernel=...) -> result`。
`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（伏特，默认 `1e-12`）与
`reltol`（无量纲，默认 `1e-10`），例如 `solve(..., vabstol=1e-9, reltol=1e-6)`。
保留 `absolute` / `relative` 作为对应旧名称；同一容差不能同时提供新旧名称。
Python 前端与 Rust 内核须一起升级到 0.7.0 / IR v7；旧 IR 应从原始 VA 重新编译。
Rust 库接口：`Circuit::new(...)` 和无状态的 `Circuit::solve(inputs)`。
独立 Rust 进程也校验 IR，不能依赖 Python 已验证输入。

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块依赖 IR 和表达式校验，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份沿用 v2；表达式、事件与算子使用 IR v7，序列化迁移规则见下文。

当前用 JSON 进程接口使 IR 易于检查，避免先复制旧的复杂 FFI。
本轮性能检查仅覆盖 Rust 库内工作点求解，未测 Python/JSON 进程接口的端到端吞吐量。

## 本地求解性能检查

`rust_core/benches/static_solver.rs` 提供无额外依赖的 Rust 库内基准：

```sh
cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=chain-64 EVAS_BENCH_SAMPLES=1024 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
```

覆盖 1/16/64/128 个未知量的仿射链、64 维稠密仿射网络和 1/16/64 维独立三次方程。
每个电路先核对独立递推/解析/二分答案；每轮新建电路，单独计时准备和首次求解，
再交替使用四个输入测量重复求解。输出包含原始计时数组，不设跨机器性能通过阈值。

下表复用父分支 0.3.2 的测量，尚不是事件执行性能测试。父分支在本机 release 构建中以相同基准比较 `d4f873d`（0.3.1）和 0.3.2；交替执行三对新旧进程，
每次五轮、每轮 1,024 点，下表为 15 轮的每点耗时中位数，单位 µs。

| 合成网络（后缀为未知量数） | 0.3.1 | 0.3.2 | 耗时比 |
| --- | ---: | ---: | ---: |
| chain-1 | 0.171 | 0.107 | 1.60× |
| chain-16 | 3.112 | 0.598 | 5.20× |
| chain-64 | 106.454 | 6.604 | 16.12× |
| chain-128 | 777.205 | 26.552 | 29.27× |
| dense-64 | 109.844 | 6.532 | 16.82× |
| cubic-1 | 3.485 | 2.735 | 1.27× |
| cubic-16 | 58.797 | 38.243 | 1.54× |
| cubic-64 | 901.317 | 803.171 | 1.12× |

这只证明所列本机合成网络的重复求解加速；不包含首次分解、Python 编译或 JSON 进程传输，
也不是 Spectre 对比。首次求解仍需分解，并保留一份稠密因子，缓存额外空间为 O(mn)
（m 条约束、n 个未知量）；没有引入稀疏后端、SCC 分块或降低收敛精度。
首次仿射求解在本轮测量中略慢，例如 64 维链从约 109.46 µs 变为 115.25 µs；
主要收益来自同一电路的多次求解，不能把表中倍率用于单次调用。
平台、编译器、原始计时、源文件/二进制哈希和阶段测量保存在该提交的本地运行归档；
可追溯摘要见 PR。当前只优化已确认的重复分解与重复表达式/Jacobian 计算。

## 实现范围

- 一个源文件一个 module，标量端口及内部 `electrical` 节点，显式方向声明。
- 文件前部可使用标准 `constants.vams` / `disciplines.vams` include 拼写。
  本切片把它们视为内建电气前导声明，不搜索外部文件；不提供常量宏展开。
- `parameter real` 默认值、实例覆盖以及参数依赖，有限实数与 SI 后缀。
- 一个 `analog begin ... end`，含无条件 `V(p)` / `V(p,n)` 贡献，以及下述限定事件块。
- 表达式支持括号、单目正负、加减、乘法及非零常数分母。
- `pow(base, exponent)` 的指数须在实例绑定后为 **1–32 的整数常数**，支持负数、零和正数底数；
  该界限是本内核的实现范围，不声称覆盖完整 `pow`。变量、分数、零和负指数仍拒绝。
  数学函数的语言来源见 [LRM 2.4 数学函数表](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)。
- manifest 提供平面实例和端口到全局网络的显式映射。内部节点使用实例私有名称。
- 全局 `0` 为固定地；其他驱动节点由调用者显式指定。每个样本提供完整驱动值。

瞬态贡献可使用 `idt(direct_affine_input, constant_ic)`，对连续 PWL 直接输入分段解析积分。
每个调用点独立，历史误差参与电压验收。缺省初值、复位、内部节点/状态输入、嵌套、积分反馈和
积分输出驱动 cross 仍拒绝；数学与限制见[算子手册](docs/OPERATORS.md#idt)。

当前拒绝事件块之外的过程赋值、条件、循环、层次实例、数组、命名支路、电流贡献、
`pow` 之外的数学函数、未列明的事件和动态算子、其他预处理指令、参数范围和未知语法。
支持集按语法和语义决定，运行时代码不读取验证集，也不识别模型/条件名称。
两个不同的本地贡献支路因端口连接而变成同一节点对时，本批显式拒绝，
避免把未经验证的别名语义解释成相加。后续扩展需单独建立契约。

## 参数绑定契约

这是当前切片的明确行为约定，不是完整 Verilog-A LRM 合规认证。

1. 所有默认表达式必须通过限定语法检查，数值字面量必须有限，名字必须已声明，
   不能引用节点电压。即使参数被覆盖或没有用于贡献，这些结构检查仍执行。
2. 对每个实例先应用覆盖值，再求其有效依赖图。覆盖值替代对应默认表达式，
   该默认表达式的算术和依赖边不再求值；其他参数读取覆盖后的值。
3. 所有参数（包括未用于贡献的参数）的有效依赖必须无环、可求值且结果有限。
   覆盖值只接受可表示为有限浮点数的 Python int/float，不接受 bool 或字符串。
4. 每个实例独立求值与缓存；源码中的声明先后顺序不影响依赖绑定。

| 默认声明 | 实例覆盖 | 当前契约 |
| --- | --- | --- |
| `a=0; b=1/a` | `a=2` | 接受，`b=0.5`；无覆盖则拒绝除零 |
| `a=1/0` 或 `a=1e308*10` | `a=2` | 接受，未执行被替换的算术；无覆盖则拒绝 |
| `a=b+1; b=a+1` | `a=2` | 接受，`b=3`；无覆盖则拒绝循环 |
| `a=missing`、`a=V(u)`、`a=1e999` | `a=2` | 仍拒绝，覆盖不能隐藏结构错误或非有限字面量 |

## IR 与贡献契约

IR v7 保留每条贡献，其 RHS 是带 `op` 标签的表达式，不含“直接写节点”指令。
`affine` 叶子保存有限常数和不重复的节点系数；`add` / `multiply` 含 `left` / `right`；
`power` 含 `base` 和整数 `exponent`。Rust 递归检查所有节点、指数和字段，不能绕过前端注入非法表达式。
每条贡献有源码文件、行列、实例以及本地支路身份。

`branch` 保留结构化身份，例如：

```json
{"instance": "dut", "local_positive": "r", "local_negative": "y", "kind": "voltage"}
```

本地端点为非空名称，按字典序排列（允许相等），`0` 表示地。贡献外层的
`positive` / `negative` 是这两个本地端点绑定后的全局节点索引，顺序对应，
RHS 已按规范方向调整符号。`kind` 目前只允许 `voltage`。
归并键是整个支路身份；`origin.instance` 仅保留诊断来源，必须与身份中的实例一致。

Rust 独立检查同一实例内本地端点的绑定一致性、地绑定和规范方向。
同一身份不能绑定不同端点；不同本地贡献支路不能因连接成为同一全局节点对。
这些检查不扩展端口别名、命名支路、电流贡献或层次结构的支持范围。

1. 前端按本地节点名固定支路方向；反向贡献同时翻转 RHS 的符号。
2. Rust 按结构化支路身份汇总所有贡献，得到一条支路电压方程。
3. 不同实例即使接到相同外部节点，也保留各自的电压约束。
4. 每次计算由完整方程求解，无旧节点值代入路径，也无自动退回旧 EVAS 的分支。

例如 `V(y,r)<+V(u,r); V(y,r)<+0.125;` 形成
`V(y)-V(r) = V(u)-V(r)+0.125`。
`V(y,r)<+V(u,r)+k*V(y,r);` 形成
`(1-k)*(V(y)-V(r)) = V(u)-V(r)`。
这两种写法使用同一组装与求解入口。

### v1/v2/v3/v4/v5/v6 → v7 迁移

Python 包与 Rust 内核一起升级到 0.7.0；Program 和成功 Response 的
`schema_version` 均为 7。Python 适配器拒绝其他响应版本。
内核 CLI 在解码贡献字段前检查整数版本号：v1/v2/v3/v4/v5/v6 或未知版本返回
`unsupported_ir_version`；缺失/错误类型及 v7 格式错误返回 `invalid_request`。
Rust 库的构造入口也检查版本。

已有 v1/v2/v3/v4/v5/v6 JSON 应从原始 VA 和 manifest 重新编译；不提供自动猜测或字符串拆分迁移。
旧归档保持原样，复现时使用旧提交对应的前端和内核。旧内核也不能执行 v7 请求。不要只修改版本号：v3 引入表达式标签，v4 引入实例状态和事件，v5 将触发器放入带 kind 标签的 trigger，v6 增加有实例/调用点身份的 operators 和 operator 引用，v7 增加 `kind=idt,input,ic,origin`。
`Program.states/events/operators` 为空时保持静态语义；省略这些字段也只表示空列表，不推断任何事件。
`state` 表达式保存状态索引，状态含实例身份、名称、类型及初始化常数；事件统一为 `trigger/assignments/origin`。
`trigger.kind=cross` 携带 guard、方向和两项容差；`trigger.kind=timer` 携带
`start/period/time_tolerance/enabled`，其中 enabled 是布尔值，省略的 VA 周期归一化为 0。
Rust 独立验证这些字段并拒绝未知或交叉混入的字段；静态入口拒绝含状态/事件/算子的程序。
事件记录增加 `kind=cross|timer`，只有 cross 含 `guard_value`；timer 不伪造 guard。

## 求解和错误

当前数学模型、Newton 验收、失败分类及稀疏分支边界统一维护在
[数值求解手册](docs/NUMERICS.md)。此标题保留旧入口链接。

## PWL 与事件的执行契约

PWL/cross、固定 timer、顺序赋值、同刻联立、误差认证与提交/回退统一维护在
[事件手册](docs/EVENTS.md)。该手册区分当前实现、历史结果与已知 Spectre 版本差异。

### 固定 timer

固定参数、名义日程及边界顺序见[事件手册](docs/EVENTS.md#固定-timer)。

## 固定 slew 执行契约

`slew(input, rise, fall)` 要求显式、固定且有限的 `rise > 0`、`fall < 0`，单位为输入单位/秒。
输入仅接受直接驱动节点与常数的仿射组合，初值为 `y(0)=input(0)`；
不接受内部节点、状态输入、嵌套算子、反馈、动态限速、缺省参数或含跳变的输入。
结构依赖检查在系数绑定前进行，零乘数或相消不能隐藏这些依赖。
贡献仍须对电压、状态及算子值联合仿射；算子输出直接或经电压网络影响 `cross` guard 时明确拒绝。

输出低于输入时以 `rise` 追赶，高于输入时以 `fall` 追赶；相等时跟踪输入斜率，
并将斜率限制到 `[fall,rise]`。因此输入进入平台后输出仍会追赶；输入斜率反向时，
输出也不立即反向，而是在两条轨迹实际相交后重新选择模式。
`slew.rs` 由输入语义拐点预先构造分段直线及追赶交点，查询不修改历史；
输出网格和 `max_step` 不参与历史定义。实例和调用点各持有自己的不可变轨迹，
与公共算子容器一同进入候选帧和原子提交。

使用向外舍入的区间判断模式、分母符号和交点次序。不能证明交点位于段内、不能与拐点分离、
不能推进可表示时间或运算溢出时返回 `event_resolution`，不以固定 epsilon 猜测。
可证明交点在当前段外时不计算可能溢出的时间商。精确相交于输入拐点时只保留该拐点。
公共绑定器在源拐点的并集求值，同时包围原始 binary64 PWL 与仿射输入表达式的实数值，
不把已舍入的中间点当作精确输入。追赶交点保存为输入段起点加局部偏移；仅调度器使用绝对代表时间。
算子值的包围区间覆盖输入、追赶、反向及已完成端点，并传入同刻电压/状态验收；
不确定模式切换处包围相邻两条轨迹。不能满足电压预算时返回 `waveform_accuracy`，不提交候选。
数学、已知大时间反例及证据边界见[算子手册](docs/OPERATORS.md#slew)。

IR v6 的 `Program.operators` 增加 `kind=slew,input,rise,fall,origin`，沿用按调用点索引的 `operator` 表达式。

初版新增 11 项 Python 开发回归及 5 项 Rust 测试。独立 `Fraction` 答案覆盖平台追赶、
反向后的两次相交、正常跟踪；另外检查反射、SI/二进制尺度、非零初值、直接驱动仿射组合、
实例隔离、网格/步长不变性、精确拐点和等限速、范围外输入及原始 IR、溢出和不可判次序，
并拒绝通过另一实例中的相消/零乘数隐藏的算子 guard 依赖。
新增[组合回归](tests/test_timed_composition.py)以独立 Fraction 公式核对双实例中的 transition、absdelay、slew、timer 与 cross：
两种实例次序 × 两种输出网格 × 两种步长共 8 配置；含同刻更新、算子输出采样和实例状态隔离。
这些检查不增加原 31 条件分母。另行完成的 [slew 专项](../experiments/pr14-pr15-validation/RESULTS.md)中，EVAS 16/16、Spectre 10/16 满足有限观测目标；保留反向追赶差异及只改变步长的诊断，不宣称完整跨后端资格。

## 扩展与验证边界

### 固定 absdelay

支持 `absdelay(input,tau)`，输入为直接驱动的连续 PWL 电压及其仿射组合，tau 是
有限的实例常数。标准范围 tau>0；tau=0 是 EVAS 的恒等扩展，不能据此要求其他后端接受。
关系为 `y(t)=input(max(t-tau,0))`，初始历史保持真实输入初值；tau 大于 stop 时仍保持初值。
调用点与实例各自持有不可变输入段；试算帧通过共享只读历史复制，不从输出样点建立历史。
内部节点、状态输入、嵌套、跳变输入、动态延迟、maxdelay 和含算子的反馈仍拒绝。
贡献保持对电压、状态和算子值联合仿射；依赖检查先于数值绑定，抵消、零缩放和下溢不能隐藏内部依赖。

内核把源拐点后移 tau 加入求解断点，输出进入电压方程并通过残差与历史前向误差验收。
输入并集拐点上的源插值、仿射运算及延迟查询保留向外舍入区间；验收计入电压网络放大，
被事件采样的状态继续保存历史误差。不能满足预算时返回 `waveform_accuracy`，不提交候选。
断点的 binary64 舍入只决定额外求解时刻，不改变 `value(t)` 使用的输入历史：
查询时保留 `t-tau` 的补偿低位，在源段内用局部时间差插值，避免大绝对时间吞掉小延迟。
后移断点溢出或重合、无法保持严格时序时返回 `time_resolution`；这包括部分保守拒绝。
此处不宣称连续时间误差资格；依赖算子输出的 cross guard（含间接电压依赖）仍明确拒绝，
不能把这些舍入后的断点当作已认证的下游事件时刻。

可运行示例：

```sh
PYTHONPATH=evas/src python3 -m evas transient evas/examples/absdelay.json --kernel evas/rust_core/target/debug/evas-kernel
```

示例输入在 0–4 ns 从 -1 V 升至 1 V，延迟 3 ns；0、3、5、7、10 ns 的独立答案为
-1、-1、0、1、1 V。`test_absdelay.py` 的开发检查覆盖该答案、零延迟扩展、仿射多源、
双实例、稀疏输出/步长不变性、断点调度、原始 IR 拒绝、失败请求及大时间局部延迟。
这些是本地开发回归。另行完成的 [absdelay 专项](../experiments/pr14-pr15-validation/RESULTS.md)中，PR14 完整前端与内核、Spectre 各 12/12 满足有限观测目标；不构成通用语言或连续时间资格。

新语义沿用同一套 IR 和执行内核。事件提交/撤销已有上述限定契约；
动态历史和更一般的事件/非线性能力仍需独立建立收敛及时间定位边界。
代码按语法、绑定、组装与数值求解分工；具体扩展先建立独立契约，再修改对应模块。

[独立验证集](validation/README.md) 的需求、答案和判据独立于 EVAS 实现。
现有 31 条已参与诊断，属于开发回归；最终评估需另设事先冻结的确认集。
[四后端基线](../experiments/dvs2-four-backend-validation/README.md) 测的是旧 EVAS 0.8.7，
不能与本静态子集直接比较总分。应用任务回归也不能代替语义正确性验证。

本前端和内核为新实现。旧源码审查来源及其构建身份限制见
[诊断记录](../experiments/dvs2-four-backend-validation/DIAGNOSIS.md)；旧仓库及部署镜像保持原样。
阶段设计和 review 讨论留在提交及 PR 历史，本页维护当前可用接口与契约。


## transition 波形算子

支持贡献表达式中的 `transition(input, td, tr, tf)`，四个参数须显式提供；
`td>=0`、`tr>0`、`tf>0` 为有限实例常数。input 只接受本实例已初始化状态和常数的仿射组合。
电压输入、嵌套算子、动态参数、默认/零边沿、状态与电压/算子乘积均明确拒绝。

```sh
PYTHONPATH=evas/src python3 -m evas transient evas/examples/transition_pulse.json --kernel evas/rust_core/target/debug/evas-kernel
```

数学、同刻联合求解、延迟队列、期限认证与拒绝边界统一见[算子手册](docs/OPERATORS.md#transition)。
本次同步已合入的 PR12；新目标来自事件后的自洽电压，算子值参与电压求解，历史整批提交。
有限对照及来源见 [PR13 验证记录](../experiments/dvs2-spectre-validation/README.md#pr13-transition-061)。
