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

这些能力有输入依赖、初值、参数和组合限制，不能由单个算子支持推导任意组合都支持。
[能力表](docs/CAPABILITIES.md)列出具体支持与缺口；
[连续动态手册](docs/CONTINUOUS.md)说明反馈、DAE 和事件组合边界。
当前实现为 **EVAS 0.12.2 / IR v16**，由 [PR33](https://github.com/BucketSran/vaEVAS/pull/33)
合并，尚未发布版本 tag。

## 构建与运行

需要 Python 3.10+ 和 Rust/Cargo。以下命令从仓库根目录运行。
先构建内核，再求解一个静态示例：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_sum.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

结果以 JSON 输出，包含节点顺序和各样本电压。
[static_sum.json](examples/static_sum.json) 的三个样本中，`out` 约为
`0.225 V`、`1.825 V`、`-0.325 V`；`ref` 的变化也参与支路电压方程。

只查看编译后的 IR，或运行带积分历史的瞬态示例：

```sh
PYTHONPATH=evas/src python3 -m evas compile evas/examples/static_sum.json
PYTHONPATH=evas/src python3 -m evas transient evas/examples/idt.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

积分示例的五个观察点输出约为 `0.25`、`0.40`、`0.45`、`0.40`、`0.25 V`。
输入从正值线性降至负值，输出先增加、再减少，停止时回到初值。

manifest 声明源文件、实例参数和端口到全局网络的映射。
静态入口提供驱动节点与样本；瞬态入口提供 PWL 源、观察时间和停止时间。
`solve` 不推进历史；含状态、事件或历史算子的模型使用 `transient`。
更多可运行输入在 [examples/](examples/)：

| 示例 | 说明 |
| --- | --- |
| [static_nonlinear.json](examples/static_nonlinear.json) | 多项式电压关系的工作点 |
| [cross_counter.json](examples/cross_counter.json) | 输入过阈值后更新计数状态 |
| [timer_counter.json](examples/timer_counter.json) | 固定定时事件 |
| [transition_pulse.json](examples/transition_pulse.json) | 有限上升/下降沿 |
| [absdelay.json](examples/absdelay.json) | 延迟历史查询 |
| [idt.json](examples/idt.json) | 连续输入积分 |

## 精度与结果解释

`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（默认 `1e-12 V`）
与 `reltol`（默认 `1e-10`，无量纲）。这两个数字是求解/验收设置，
不能直接解释为所有输出都具有同样的全时域精度。
静态 Newton 检查原方程残差；瞬态还要考虑输入、历史、采样及事件时刻的误差和网络放大。
具体判据、保守拒绝和数值方法见[数值手册](docs/NUMERICS.md)。

旧 IR 1–15 必须从原始 VA/manifest 重新编译；前端与内核需要配套。
批量工具和兼容性规则见[IR 版本与迁移](#ir-v8-migration)。

## 验证与开发

[独立验证集](validation/README.md)维护模型契约、数学答案和判据。
[当前执行证据](../experiments/parallel-gap-integration/README.md#当前证据)记录原 31 条件
两档回放及实际被测源码/内核身份。有限观测达标不等于完整 Verilog-A 合规、
连续时间资格或性能领先；详细结果与历史失败分别保留。

从仓库根目录运行开发检查：

```sh
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
cargo test --locked --manifest-path evas/rust_core/Cargo.toml
```

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

动态算子的精确支持范围见[算子手册](docs/OPERATORS.md)；事件语义与同刻求解见
[事件手册](docs/EVENTS.md)。未列明的合法 VA 写法也可能是当前能力缺口，
不应把实现拒绝解释为语言标准禁止。
仍拒绝超出范围的循环、层次实例、通用数组、命名支路、电流贡献、通用预处理等。
不同本地贡献支路因端口连接成为同一节点对的情况也明确拒绝，等待独立契约验证。

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

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块依赖 IR 和表达式校验，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份沿用 v2；当前实现表达式、事件与算子使用 IR v16，序列化迁移规则见下文。

当前用 JSON 进程接口使 IR 易于检查，避免先复制旧的复杂 FFI。
已有性能检查只覆盖对应历史检查点的 Rust 库内工作点求解，未测 Python/JSON 进程接口的端到端吞吐量。

<details>
<summary>源码模块职责表</summary>

| 模块 | 当前文件 | 唯一职责 |
| --- | --- | --- |
| 语法解析 | `src/evas/syntax.py` | 完整消费 token，生成带源码位置的语法树 |
| 语义绑定 | `src/evas/frontend.py` | 绑定参数、实例与节点，建立贡献支路身份 |
| 表达式转换 | `src/evas/lowering.py` | 常量折叠，生成仿射叶子与多项式表达式 |
| IR | `src/evas/ir.py`、`rust_core/src/ir.rs` | Python/Rust 之间带版本和源码位置的数据契约 |
| 方程组装 | `rust_core/src/assembly.rs` | 校验 IR 与驱动配置，累加支路贡献，生成方程系数及节点分区 |
| 工作点求解 | `rust_core/src/solver.rs` | 代入每个样本的驱动值，求解未知电压，验收原方程残差 |
| 表达式求值 | `rust_core/src/expression.rs` | 递归校验 IR，计算多项式值与链式法则导数 |
| 无状态瞬态与普通条件 | `rust_core/src/analog.rs` | 从 PWL 区间认证选支；仿射模型复用原 IR 前向映射，多项式模型使用 Newton，并在规定边界内作根盒认证 |
| 非线性求解 | `rust_core/src/nonlinear.rs` | 对同一组支路方程执行有界阻尼 Newton 迭代 |
| 线性代数 | `rust_core/src/linear.rs`、`linear/dense.rs`、`linear/sparse.rs`、`linear/columns.rs` | 稠密/稀疏分流、行缩放、选主元、列排序与多 RHS 求解 |
| 事件语义 | `rust_core/src/events.rs` | 校验状态/事件身份及依赖，将状态代入方程，准备事件块的状态更新 |
| 条件执行 | `rust_core/src/event_conditions.rs` | 全路径结构检查、可达谓词认证、选中路径与缓存身份 |
| 事件误差界 | `rust_core/src/event_accuracy.rs` | 从原 IR 包围仿射网络的传递系数，复核状态独立性及冗余约束 |
| 区间算术 | `rust_core/src/interval.rs` | 向外舍入的 binary64 四则运算及精确乘积比较 |
| 连续输入与根 | `rust_core/src/pwl.rs` | 校验连续 PWL、求值、识别方向及区间内孤立根 |
| 同刻求解 | `rust_core/src/settlement.rs` | 联立仿射事件更新与电压方程，重放原赋值并校验一致性 |
| 同刻误差认证 | `rust_core/src/settlement_bounds.rs` | 从原 IR 独立包围事件后解，检查电压与状态各自误差预算 |
| 仿射区间运算 | `rust_core/src/affine_bounds.rs` | 定位与同刻认证共用的向外舍入转换和消元 |
| 事件日程 | `rust_core/src/schedule.rs` | 生成 cross/timer 统一日程，验证定位误差、同刻关系、次序与事件预算 |
| 波形算子 | `rust_core/src/operators.rs`、`transition.rs`、`absdelay.rs`、`slew.rs`、`idt.rs`、`laplace.rs`、`idtmod.rs` | 校验独立调用点/输入，保存延迟、边沿、限速、积分/滤波/相位历史；`operators.rs` 计算受限 sin 的值与包络 |
| 连续动态 | `continuous.rs`、`continuous_runtime.rs`、`continuous_history.rs`、`continuous_derivatives.rs`、`nonlinear_dynamics.rs`、`state_space.rs`（均在 `rust_core/src/`） | 仿射电压关系、导数质量关系、线性/多项式传播和候选历史 |
| 动态 guard | `rust_core/src/guard_trajectory.rs`、`dynamic_roots.rs` | 连续值/导数包围，区间隔离并认证多项式与算子驱动 cross |
| IR 重编译 | `src/evas/migrate.py`、`../scripts/recompile_evas_manifests.py` | 从原始 manifest/VA 真正重编译，独占新目录并记录源身份 |
| 时间推进 | `rust_core/src/transient.rs` | 候选试算、原子提交、输出实际接受的事件记录 |
| 进程接口 | `src/evas/runtime.py`、Rust `main.rs` | 一个批次一次 JSON 请求，无 Python 求值回调 |
| 用户入口 | `src/evas/__main__.py` | 读取显式平面电路 manifest，输出 IR 或结果 |

</details>

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

仓库可运行 manifest 的默认范围为 `evas/examples/`。批量工具读取原 VA 和实例参数，写入新的 IR16，
保留每项 manifest/source SHA256 及失败诊断；原 IR、历史波形和收据不改写：

```sh
python3 scripts/recompile_evas_manifests.py --output runs/recompile-ir16
python3 scripts/recompile_evas_manifests.py --output runs/recompile-selected evas/examples/idt.json
```

输出目录必须不存在；部分失败返回非零，成功项仍保留。没有原始 VA/manifest 的旧 IR 无法凭改版本号迁移。

更严格的瞬态认证会改变部分接受范围：多项式非方阵在点输入也拒绝；仿射冗余关系必须
在误差映射的参数域上成立，不能只在某个状态点碰巧一致。通用 `real` 状态目前使用相对误差预算，
接近零的非点状态可能保守拒绝。静态 `solve` 仍是局部 Newton 验收，没有同等根前向误差证书。
这些是明确实现边界，详见[精度链与兼容性](../experiments/parallel-gap-integration/REVIEW.md#precision-chain)。
旧归档使用对应提交的前端和内核复现；[历史 v9 迁移说明](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#ir-v8-migration)保留原身份。

`Program.states/events/operators` 为空时保持静态语义；省略这些字段也只表示空列表，不推断事件。
`state` 表达式保存状态索引，状态含实例身份、名称、类型及初始化常数；事件为 `trigger/body/origin`。
body 的 `kind=assign` 含 `state/rhs`；`kind=if` 含 `relation/left/right/then_body/else_body/origin`，
relation 为 `lt/le/gt/ge`。无 else 序列化为空 body；未知字段、关系或缺失 body 均拒绝。
trigger 支持 cross、固定 timer 和仅含 cross 叶子的 OR；格式、身份与事件记录见[事件手册](docs/EVENTS.md#event-or)。
算子按实例/调用点引用，idt 的可空 reset 字段见[算子手册](docs/OPERATORS.md#idt)。
静态入口拒绝含状态、事件或算子的程序；完整字段定义见[Python IR](src/evas/ir.py)与[Rust IR](rust_core/src/ir.rs)。

</details>

<details>
<summary>Rust 库内性能检查</summary>

## 本地求解性能检查

[static_solver.rs](rust_core/benches/static_solver.rs) 提供 Rust 库内构造解核对和局部计时：

```sh
cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=chain-64 EVAS_BENCH_SAMPLES=1024 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
```

基准的准备/首次/重复求解边界、稠密/稀疏分流及局限统一见[数值手册](docs/NUMERICS.md#稀疏分支与性能边界)。
旧 0.3.1/0.3.2 的重复求解比较保留在[固定历史记录](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#本地求解性能检查)，
不代表当前版本、首次求解、瞬态或跨后端速度。

</details>
