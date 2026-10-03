# EVAS：电压域 Verilog-A 仿真器

EVAS 把限定范围内的 Verilog-A 电压关系编译为方程，联立求解节点电压。
它适合描述理想电压域行为，例如增益、限幅、采样、事件计数和连续时间算子。
它不包含晶体管器件模型、电流/电荷方程或完整 SPICE 网表求解。

前端使用 Python 解析、绑定并生成 IR，Rust 内核完成求解与时间推进。
同一支路的多条贡献会相加；程序赋值则保留顺序语义。
瞬态试算从已接受历史出发，电压、状态和误差检查通过后一起提交。

## 可以做什么

| 功能 | 使用方式与边界 |
| --- | --- |
| 静态电压方程 | `solve` 独立求每个样本的工作点；支持仿射关系和受限多项式非线性 |
| 瞬态输入与事件 | `transient` 推进 PWL 输入、`cross`、固定 `timer`、事件体条件与顺序赋值 |
| 波形与历史算子 | 受限 `transition`、`absdelay`、`slew`、`idt`、`idtmod`、`laplace_nd` 和 `ddt` |
| 连续动态反馈 | 在声明的边界内联合处理积分、滤波、导数关系和非线性动态 |
| 精度控制 | 电压容差、历史误差传播、事件时刻/条件认证；不能证明预算时明确拒绝 |
| 诊断与来源查询 | 可选、有预算的试算/提交记录，编译 IR 静态查询，以及单会话只读 stdio MCP；缺少证据时明确返回未知 |

查询入口和身份/截断规则见[诊断说明](docs/diagnostics.md)。
Rust 的版本化类型与解码位于 [evas-ir](rust_core/ir/README.md)，数值与历史仍由一个内核统一管理。
配对测量与结构取舍见[性能实验](../experiments/performance/README.md)。

这些能力有输入依赖、初值、参数和组合限制，不能由单个算子支持推导任意组合都支持。
[能力表](docs/CAPABILITIES.md)列出具体支持与缺口；
[连续动态手册](docs/math/continuous.md)说明反馈、DAE 和事件组合边界。
当前实现为 **EVAS 0.12.3 / IR v16**；改动摘要见[更新记录](docs/UPDATE.md)，尚未发布版本 tag。

## 构建与运行

需要 Python 3.10+ 和 Rust/Cargo。以下命令从仓库根目录运行。
先构建内核，再求解一个静态示例：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas solve evas/examples/01-static-gain/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

结果以 JSON 输出，包含节点顺序和各样本电压。
[第 1 课](examples/01-static-gain/README.md)的三个样本中，`out` 约为
`0.225 V`、`1.825 V`、`-0.325 V`；`ref` 的变化也参与支路电压方程。

只查看编译后的 IR，或运行带积分历史的瞬态示例：

```sh
PYTHONPATH=evas/src python3 -m evas compile evas/examples/01-static-gain/sim.json
PYTHONPATH=evas/src python3 -m evas transient evas/validation/smoke/idt.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

积分示例的五个观察点输出约为 `0.25`、`0.40`、`0.45`、`0.40`、`0.25 V`。
输入从正值线性降至负值，输出先增加、再减少，停止时回到初值。

manifest 声明源文件、实例参数和端口到全局网络的映射。
静态入口提供驱动节点与样本；瞬态入口提供 PWL 源、观察时间和停止时间。
`solve` 不推进历史；含状态、事件或历史算子的模型使用 `transient`。
[examples/](examples/) 按三课组织（静态求解 → 瞬态与历史 → 事件），
每课自带电路图、va/json 字段对照与期望输出；覆盖各条仿真能力路径的最小冒烟集
（静态非线性、连续积分、延迟历史、定时/过阈事件、有限边沿）见
[validation/smoke/](validation/smoke/)：

| 冒烟输入 | 说明 |
| --- | --- |
| [static_nonlinear.json](validation/smoke/static_nonlinear.json) | 多项式电压关系的工作点 |
| [cross_counter.json](validation/smoke/cross_counter.json) | 输入过阈值后更新计数状态 |
| [timer_counter.json](validation/smoke/timer_counter.json) | 固定定时事件 |
| [transition_pulse.json](validation/smoke/transition_pulse.json) | 有限上升/下降沿 |
| [absdelay.json](validation/smoke/absdelay.json) | 延迟历史查询 |
| [idt.json](validation/smoke/idt.json) | 连续输入积分 |

## 精度与结果解释

`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（默认 `1e-12 V`）
与 `reltol`（默认 `1e-10`，无量纲）。这两个数字是求解/验收设置，
不能直接解释为所有输出都具有同样的全时域精度。
静态 Newton 检查原方程残差；瞬态还要考虑输入、历史、采样及事件时刻的误差和网络放大。
具体判据、保守拒绝和数值方法见[数值手册](docs/math/solving.md)。

旧 IR 1–15 必须从原始 VA/manifest 重新编译；前端与内核需要配套。
批量工具和兼容性规则见[IR 版本与迁移](#ir-v8-migration)。

## 验证与开发

[独立验证集](validation/README.md)维护模型契约、数学答案和判据。
[当前执行证据](../experiments/runs/parallel-gap-integration/README.md#当前证据)记录原 31 条件
两档回放及实际被测源码/内核身份。有限观测达标不等于完整 Verilog-A 合规、
连续时间资格或性能领先；详细结果与历史失败分别保留。

从仓库根目录运行开发检查：

```sh
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
cargo test --locked --manifest-path evas/rust_core/Cargo.toml
```

[CI 工作流](../.github/workflows/numerical-assurance.yml)在 EVAS、实验工具或维护脚本变更时，
运行完整 Python/Rust 回归、Clippy、格式、追溯矩阵、冻结身份及独立数学/检查器校准。
另外运行 ngspice 共同子集和有界 fuzz。回归使用 Python 3.12、Rust stable，fuzz 使用 nightly；
它不覆盖所有操作系统/工具链，也不自动执行 Spectre 或原 31×2 矩阵。
各次矩阵执行与正式资格边界仍以具名收据为准。

静态回放工具 [run_static_regression.py](tests/run_static_regression.py) 检查符合静态入口的
原矩阵模型；两档的采样点与残差检查不能替代瞬态事件验证。
新增能力需要同时说明数学含义、状态生命周期、组合边界和独立答案，要求见
[技术手册](docs/README.md#feature-documentation-contract)。

## 实现范围

- 一个源文件一个 module，标量端口及内部 `electrical` 节点，显式方向声明。
- 文件前部可使用标准 `constants.vams` / `disciplines.vams` include 拼写。
  本切片把它们视为内建前导声明，不搜索外部文件；当前只识别有限常量 `` `M_PI``，不提供通用宏处理。
- `parameter real` 默认值、实例覆盖以及参数依赖，有限实数与 SI 后缀。
- 一个 `analog begin ... end`，含无条件 `V(p)` / `V(p,n)` 贡献，以及受限事件块。
- 表达式支持括号、单目正负、加减、乘法及非零常数分母。
- `pow(base, exponent)` 的指数须在实例绑定后为 **1–32 的整数常数**，支持负数、零和正数底数；
  该界限是本内核的实现范围，不声称覆盖完整 `pow`。变量、分数、零和负指数仍拒绝。
  数学函数的语言来源见 [LRM 2.4 数学函数表](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)。
- manifest 提供平面实例和端口到全局网络的显式映射。内部节点使用实例私有名称。
- 全局 `0` 为固定地；其他驱动节点由调用者显式指定。每个样本提供完整驱动值。
- 本分支候选新增 real 输入的纯 `analog function`：局部顺序赋值、模块参数和受限嵌套调用。
  函数在绑定前展开为同一关系 IR；不含电压访问、历史调用或递归。范围与独立答案见
  [函数展开契约](validation/ANALOG_CONDITIONS_CONTRACT.md#纯函数的分支候选)。候选尚未合并。

本分支候选同时允许实例常量控制的 `genvar for`，在编译时展开顺序赋值和累加贡献。
总迭代与展开语句各限 4096；循环内历史调用、运行时循环和数组索引仍拒绝。
范围与独立答案见[循环展开契约](validation/ANALOG_CONDITIONS_CONTRACT.md#静态-genvar-循环的分支候选)。

动态算子的精确支持范围见[算子手册](docs/math/operators.md)；事件语义与同刻求解见
[事件手册](docs/math/events.md)。未列明的合法 VA 写法也可能是当前能力缺口，
不应把实现拒绝解释为语言标准禁止。
仍拒绝超出范围的循环、层次实例、通用数组、命名支路、电流贡献、通用预处理等。
不同本地贡献支路因端口连接成为同一节点对的情况也明确拒绝，等待独立契约验证。

<a id="frontend-boundaries"></a>

## 前端输入与执行边界

CLI 与迁移工具共用 manifest 校验。`models` 和 `instances` 必须是非空数组；
实例的 `connections`、`parameters` 必须是对象。重复 JSON 字段和非有限数字会被拒绝，
避免后一个参数悄悄覆盖前一个。迁移中已识别的输入错误按单项记录，后续模型继续处理。

编译器有明确的资源预算。这些是实现限制，不是 Verilog-A 语言规则：

| 对象 | 当前上限 |
| --- | ---: |
| 语法递归嵌套 | 64 层 |
| 源表达式树深度 | 80 层 |
| 覆盖后有效参数依赖链 | 64 层 |
| Program 序列化容器深度 | 96 层，为 Rust 请求外层保留空间 |
| 展开后的 IR 值与容器总数 | 100,000 |

参数按有效依赖图迭代求值，声明顺序不改变依赖链限制。IR 大小检查计入每次引用的展开成本，
同时缓存子图的计算结果；不会为了估算大小而先复制整个表达式树。
超限时返回带源码位置的 `CompileError`。合法但过大的模型也可能被拒绝，
包括旧版本偶尔能处理的长表达式。本版本保持 IR16，不通过重关联算式或消去依赖绕过预算；
更大的模型需要后续共享表达式 IR 或其他有独立验证的方案。

`solve` / `transient` 的 `timeout` 默认 **300 秒**，只限制内核进程执行时间，
不包含 Python 编译与序列化。API 可传正的有限秒数，或用 `timeout=None` 关闭上限。
CLI 使用 `--timeout 600` 调整；时间超限会终止并回收内核子进程，报告 `kernel_timeout`。
仿真时间 `stop` 与这个墙钟时间上限是两个不同设置。

CLI 的内核失败在 stderr 输出 JSON，保留 `kind`、`message` 和存在时的 `sample`；
成功结果仍输出到 stdout。输入/编译错误仍是可读文本，错误退出码均为 2。
适配器验证返回结果的身份、行数、电压/状态维度及有限数值；坏响应为 `invalid_response`，
无法启动进程或不合格式的进程错误为 `kernel_process`。
这些检查保护调用边界，不代替内核的电压精度验收。

## 模块与接口

Python 的公开接口：`compile_sources(sources, instances) -> Program`，
`solve(program, driven, samples, kernel=...) -> result`，以及
`transient(program, sources, output_times, stop=..., max_step=..., kernel=...) -> result`。
`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（伏特，默认 `1e-12`）与
`reltol`（无量纲，默认 `1e-10`），例如 `solve(..., vabstol=1e-9, reltol=1e-6)`。
保留 `absolute` / `relative` 作为对应旧名称；同一容差不能同时提供新旧名称。
当前实现 Python 前端与 Rust 内核使用 IR v16；版本迁移规则见[下文](#ir-v8-migration)。
Rust 库接口：`Circuit::new(...)` 和无状态的 `Circuit::solve(inputs)`。
独立 Rust 进程也校验 IR，不能依赖 Python 已验证输入。

静态批量求解默认串行。设置 `EVAS_STATIC_THREADS=4` 可让内核并行处理独立样本，
合法线程数为 1–64；结果顺序和首个失败的样本下标不变。Rust 调用方可用
`run_with_threads(request, 4)`。瞬态仍按时间顺序推进；线程启动有开销，小批量未必更快。

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块依赖 IR 和表达式校验，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份沿用 v2；当前实现表达式、事件与算子使用 IR v16，序列化迁移规则见下文。

当前用 JSON 进程接口使 IR 易于检查，避免先复制旧的复杂 FFI。
性能基准覆盖 Rust 库内静态求解、批量并行和五类瞬态路径。
这些计时不含 Python/JSON 进程接口，不能直接代表端到端吞吐量或跨后端速度。

<a id="review-map"></a>

## 按功能审查

源码按下面六组责任阅读。表中列出入口，具体辅助模块由对应章节说明。
这些是阅读分组，当前文件路径保持原布局。

| 功能与数学入口 | 源码入口及责任 | 独立契约 | 回归入口 |
| --- | --- | --- | --- |
| 模型编译与贡献：[参数](#参数绑定契约)、[IR 与贡献](#ir-与贡献契约) | [syntax.py](src/evas/syntax.py) 解析；[frontend.py](src/evas/frontend.py) 编排；[instance_compiler.py](src/evas/instance_compiler.py) 绑定实例、参数、状态和调用点；[lowering.py](src/evas/lowering.py) 转换表达式；[Python IR](src/evas/ir.py) / [Rust IR](rust_core/src/ir.rs) 定义传输；[assembly.rs](rust_core/src/assembly.rs) 累加贡献 | 本页接口契约；[起步案例卡](validation/CASE_CARDS.md)的静态关系 | [test_contracts.py](tests/test_contracts.py)、[test_affine.py](tests/test_affine.py) |
| 电压求解与精度：[NUMERICS](docs/math/solving.md) | [solver.rs](rust_core/src/solver.rs) 工作点；[nonlinear.rs](rust_core/src/nonlinear.rs) Newton；[linear.rs](rust_core/src/linear.rs) 稠密/稀疏分流；[analog.rs](rust_core/src/analog.rs) 无状态瞬态与普通条件；[expression.rs](rust_core/src/expression.rs)、[interval.rs](rust_core/src/interval.rs)、[affine_bounds.rs](rust_core/src/affine_bounds.rs) 提供共用运算与认证 | [非线性瞬态](validation/NONLINEAR_TRANSIENT_CONTRACT.md)、[普通条件](validation/ANALOG_CONDITIONS_CONTRACT.md) | [精度](tests/test_accuracy.py)、[稀疏](tests/test_sparse.py)、[普通条件](tests/test_analog_conditions.py)、[非线性瞬态](tests/test_nonlinear_transient.py)、[精度链](tests/test_precision_chain.py) |
| 事件与同刻关系：[EVENTS](docs/math/events.md) | [events.rs](rust_core/src/events.rs) 赋值语义；[event_conditions.rs](rust_core/src/event_conditions.rs) 选支；[pwl.rs](rust_core/src/pwl.rs) 输入与仿射根；[schedule.rs](rust_core/src/schedule.rs) 日程；[event_accuracy.rs](rust_core/src/event_accuracy.rs) 定位认证；[settlement.rs](rust_core/src/settlement.rs) / [settlement_bounds.rs](rust_core/src/settlement_bounds.rs) 联立求解与误差 | [事件条件](validation/EVENT_CONDITIONS_CONTRACT.md)、[定时契约](validation/TIMED_OPERATOR_CONTRACTS.md) | [cross](tests/test_events.py)、[timer](tests/test_timer.py)、[同刻](tests/test_settlement.py)、[条件](tests/test_event_conditions.py)、[OR](tests/test_event_or.py)、[写者冲突](tests/test_event_writers.py) |
| 独立波形算子：[OPERATORS](docs/math/operators.md) | [operators.rs](rust_core/src/operators.rs) 管理调用点、值/区间查询及候选历史；各算子的文件与测试见[算子对应表](docs/math/operators.md#operator-map) | [定时算子](validation/TIMED_OPERATOR_CONTRACTS.md)、[积分](validation/DYNAMICS_CONTRACTS.md)、[低通](validation/LAPLACE_CONTRACTS.md) | 各算子回归；[定时组合](tests/test_timed_composition.py)、[语义不变性](tests/test_semantic_invariants.py) |
| 联合连续动态：[CONTINUOUS](docs/math/continuous.md) | [continuous.rs](rust_core/src/continuous.rs) 关系与 DC；[continuous_derivatives.rs](rust_core/src/continuous_derivatives.rs) 导数；[state_space.rs](rust_core/src/state_space.rs) 线性传播；[nonlinear_dynamics.rs](rust_core/src/nonlinear_dynamics.rs) 多项式传播；[implicit_dynamics.rs](rust_core/src/implicit_dynamics.rs) DAE；[guard_trajectory.rs](rust_core/src/guard_trajectory.rs) / [dynamic_roots.rs](rust_core/src/dynamic_roots.rs) 动态根 | [动态与生命周期](validation/DYNAMICS_CONTRACTS.md) | [连续关系](tests/test_continuous_dynamics.py)、[动态 cross](tests/test_dynamic_cross.py)、[动态组合](tests/test_dynamic_closure.py)、[混合算子](tests/test_mixed_dynamics.py)、[DAE](tests/test_implicit_dynamics.py) |
| 请求与接受帧：[共同生命周期](docs/math/continuous.md#shared-lifecycle-closure) | [__main__.py](src/evas/__main__.py) / [manifest.py](src/evas/manifest.py) 校验输入；[runtime.py](src/evas/runtime.py) / [protocol.py](src/evas/protocol.py) 处理进程与响应；[main.rs](rust_core/src/main.rs) 处理请求；[transient.rs](rust_core/src/transient.rs) 试算与整批提交；[continuous_runtime.rs](rust_core/src/continuous_runtime.rs) / [continuous_history.rs](rust_core/src/continuous_history.rs) 区分观察与未来历史；[reset_dependencies.rs](rust_core/src/reset_dependencies.rs) 检查复位及瞬时反馈依赖 | [共同生命周期契约](validation/DYNAMICS_CONTRACTS.md#shared-lifecycle-contract) | [观察闭包](tests/test_lifecycle_closure.py)、[事件时间盒](tests/test_event_window_sampling.py)、[已知事件截止点](tests/test_event_horizons.py)；[真实控制器回退](rust_core/src/transient_lifecycle_tests.rs) |

`tests/` 与 `validation/` 的分工：**[tests/](tests/) 是"改代码时别改坏"的护栏**——
开发回归套件，随时全量运行，期望值独立于实现但准入跟随开发节奏；
**[validation/](validation/) 是"证明它本来是对的"的证据**——固定的条件矩阵与协议，
预期结果来自模型声明的方程与状态转移，可对外引用为验证资格。
tests 通过的数目不折算为验证条件数；分组与运行方式见
[tests/README.md](tests/README.md)，两级验证目录见 [validation/README.md](validation/README.md)。

`tests/test_*.py` 从公开编译/运行入口检查行为。Rust 模块中的私有测试检查区间、缓存和候选回退；
`transient_*_tests.rs` 由 `transient.rs` 加载，部分测试直接检查接受帧，
`transient_lifecycle_tests.rs` 还检查生产控制器的游标和事件记录。
[run_static_regression.py](tests/run_static_regression.py) 与 [benchmark_events.py](tests/benchmark_events.py)
分别用于静态矩阵回放和局部事件计时，不能代替独立答案或完整瞬态验证。
迁移工具 [migrate.py](src/evas/migrate.py) 与[批量入口](../scripts/recompile_evas_manifests.py)
的规则见[IR 版本与迁移](#ir-v8-migration)，回归见 [test_migrate.py](tests/test_migrate.py)。

审查一个算子时，先确认输入依赖，再选择路径。例如，直接 PWL 的 `idt` 从
[解析公式](docs/math/operators.md#idt)和 `idt.rs` 开始；带反馈的 `idt` 从
[联合方程](docs/math/continuous.md#电压关系与积分反馈)和 `continuous.rs` 开始。
如果改动涉及事件或复位，还需检查共同生命周期与对应的失败后回退测试。
单项测试通过，不能替代这些组合义务。

<details>
<summary>参数、贡献与 IR 的详细接口契约</summary>

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

当前实现使用 IR v16，增加 ddt、连续动态网络与动态 guard，延续 v11 的 idt 复位与逐条贡献契约；每条贡献的 RHS 是带 `op` 标签的表达式，不含“直接写节点”指令。
`affine` 叶子保存有限常数和不重复的节点系数；`add` / `multiply` 含 `left` / `right`；
`power` 含 `base` 和整数 `exponent`；`select` 含比较关系、两侧表达式、两臂值与源码位置。
Rust 递归检查所有节点、指数和字段，不能绕过前端注入非法表达式。
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

<a id="ir-v8-migration"></a>

### IR 版本与迁移

Program 和成功 Response 的 `schema_version` 均为 **16**，Python 适配器与 Rust 内核同步检查。
旧版本或未知整数版本先于载荷解码返回 `unsupported_ir_version`；版本缺失/错误类型及当前格式错误返回
`invalid_request`。Rust 库构造入口也检查版本。旧 IR 1–15 的 JSON 须从原始 VA 与 manifest 重新编译，不能只改版本号。
前端与内核须配套使用，旧 IR15 内核不能消费 IR16。

仓库冒烟 manifest 的默认范围为 `evas/validation/smoke/`。批量工具读取原 VA 和实例参数，写入新的 IR16，
保留每项 manifest/source SHA256 及失败诊断；原 IR、历史波形和收据不改写：

```sh
python3 scripts/recompile_evas_manifests.py --output runs/recompile-ir16
python3 scripts/recompile_evas_manifests.py --output runs/recompile-selected evas/validation/smoke/idt.json
```

输出目录必须不存在；部分失败返回非零，成功项仍保留。没有原始 VA/manifest 的旧 IR 无法凭改版本号迁移。

更严格的瞬态认证会改变部分接受范围：多项式非方阵在点输入也拒绝；仿射冗余关系必须
在误差映射的参数域上成立，不能只在某个状态点碰巧一致。通用 `real` 状态目前使用相对误差预算，
接近零的非点状态可能保守拒绝。静态 `solve` 仍是局部 Newton 验收，没有同等根前向误差证书。
这些是明确实现边界，详见[精度链与兼容性](../experiments/runs/parallel-gap-integration/REVIEW.md#precision-chain)。
旧归档使用对应提交的前端和内核复现；[历史 v9 迁移说明](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#ir-v8-migration)保留原身份。

`Program.states/events/operators` 为空时保持静态语义；省略这些字段也只表示空列表，不推断事件。
`state` 表达式保存状态索引，状态含实例身份、名称、类型及初始化常数；事件为 `trigger/body/origin`。
body 的 `kind=assign` 含 `state/rhs`；`kind=if` 含 `relation/left/right/then_body/else_body/origin`，
relation 为 `lt/le/gt/ge`。无 else 序列化为空 body；未知字段、关系或缺失 body 均拒绝。
trigger 支持 cross、固定 timer 和仅含 cross 叶子的 OR；格式、身份与事件记录见[事件手册](docs/math/events.md#event-or)。
算子按实例/调用点引用，idt 的可空 reset 字段见[算子手册](docs/math/operators.md#idt)。
静态入口拒绝含状态、事件或算子的程序；完整字段定义见[Python IR](src/evas/ir.py)与[Rust IR](rust_core/src/ir.rs)。

</details>

<details>
<summary>Rust 库内性能检查</summary>

## 本地求解性能检查

[static_solver.rs](rust_core/benches/static_solver.rs) 提供 Rust 库内构造解核对和局部计时：

```sh
cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=chain-64 EVAS_BENCH_SAMPLES=1024 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=random-1024 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=batch EVAS_BENCH_SAMPLES=4096 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench transient_solver
```

基准的准备/首次/重复求解边界、稠密/稀疏分流及局限统一见[数值手册](docs/math/solving.md#稀疏分支与性能边界)。
旧 0.3.1/0.3.2 的重复求解比较保留在[固定历史记录](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#本地求解性能检查)，
不代表当前版本、首次求解、瞬态或跨后端速度。

</details>
