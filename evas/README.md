# EVAS

EVAS 将限定的 Verilog-A 电压贡献编译为方程，由 Rust 联立求解节点电压。
`solve` 对每个样本独立求静态工作点；`transient` 沿物理时间推进输入、事件、实例状态和算子历史。
贡献关系与程序顺序赋值分别处理，验收通过后才提交候选状态。

当前开发分支为 **EVAS 0.10.0 / IR v16**，尚未合并或发布版本 tag。支持范围和剩余缺口以
[能力表](docs/CAPABILITIES.md)为准；数学与实现从[技术手册](docs/README.md)进入。
支持受限事件体 if/else、cross OR、多事件写者、直接 PWL 积分及状态复位，
以及普通 analog 局部赋值/输入条件、一阶 `laplace_nd`、`idtmod`/受限 `sin`、无状态多项式瞬态。
每项都有组合边界；运行时不会识别验证集/模型名称，也不会自动回退到旧 EVAS 0.8.7。

瞬态的 PWL、采样状态和算子历史误差进入输出验收。多项式瞬态的点输入也要求根盒证明；
不能证明电压预算时明确拒绝。[精度链审查](../experiments/parallel-gap-integration/REVIEW.md#precision-chain)
与[最新验证](validation/README.md#latest-evas-checkpoint)绑定被测运行时 `d451605`。
旧 IR 1–15 需要重新编译，更严格认证的具体边界见[迁移说明](#ir-v8-migration)。

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
回放工具按模型是否满足静态入口契约选择接受或明确拒绝；事件与历史算子需要瞬态入口。
静态回放的历史检查数不能代替下面的新瞬态矩阵。
两档对应 4,001／40,001 点的静态采样网格和电压/残差容差，不是瞬态仿真或 DVS 正式资格。

## 回归证据

以下结果绑定已合并 IR15 检查点。IR16 的新能力与验证另见[连续动态说明](docs/CONTINUOUS.md)，不继承历史运行身份。

最新 IR16 开发运行时 `071a813` 的[初始化 review 修复收据](../experiments/parallel-gap-integration/results/continuous-initialization-review.json)
保留恒等滤波初值的反例、统一 DC 求值后的组合回归及原矩阵新执行。
原 31 条件两档均达标，CSV 与首轮 IR16 检查点一致；源码仍在开发分支，尚未合并。
首轮 `ba5ab46` 的[检查与迁移](../experiments/parallel-gap-integration/results/continuous-dynamics-checks.json)
及[原矩阵](../experiments/parallel-gap-integration/results/continuous-dynamics-matrix.json)保持原身份。

被测运行时 `d451605` 的原 31 条件两档本地瞬态回放均 **31/31 有限观测达标**，
62 份 CSV、判定与生效设置和优化检查点 `ddfd379` 一致。
**372 Python、83 Rust** 测试及 locked build、Clippy、格式检查通过；一项旧性能探针 ignored。
[矩阵与检查收据](../experiments/parallel-gap-integration/README.md#当前证据)记录精确源码、二进制与检查器身份。
这轮没有新 Spectre 执行或新性能测量；完整原始材料仅本地保留。
静态回放、开发 unittest 方法数和瞬态条件数分别报告；原条件已用于诊断，属于开发材料。
正式 DVS 资格仍 **I**，不代表完整语言合规、未见确认集或全时域精度。

历史执行与差异从[实验索引](../experiments/README.md#checkpoint-evidence)进入；
原组件的逐轮测试记录保留在[固定提交](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#回归证据)。

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
| 连续动态 | `rust_core/src/continuous.rs`、`state_space.rs` | 联立仿射电压/积分/滤波关系，区间矩阵指数传播；不可变历史查询 |
| 动态 guard | `rust_core/src/guard_trajectory.rs`、`dynamic_roots.rs` | 连续值/导数包围，区间隔离并认证多项式与算子驱动 cross |
| IR 重编译 | `src/evas/migrate.py`、`../scripts/recompile_evas_manifests.py` | 从原始 manifest/VA 真正重编译，独占新目录并记录源身份 |
| 时间推进 | `rust_core/src/transient.rs` | 候选试算、原子提交、输出实际接受的事件记录 |
| 进程接口 | `src/evas/runtime.py`、Rust `main.rs` | 一个批次一次 JSON 请求，无 Python 求值回调 |
| 用户入口 | `src/evas/__main__.py` | 读取显式平面电路 manifest，输出 IR 或结果 |

Python 的公开接口：`compile_sources(sources, instances) -> Program`，
`solve(program, driven, samples, kernel=...) -> result`，以及
`transient(program, sources, output_times, stop=..., max_step=..., kernel=...) -> result`。
`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（伏特，默认 `1e-12`）与
`reltol`（无量纲，默认 `1e-10`），例如 `solve(..., vabstol=1e-9, reltol=1e-6)`。
保留 `absolute` / `relative` 作为对应旧名称；同一容差不能同时提供新旧名称。
当前开发分支 Python 前端与 Rust 内核使用 IR v16；版本迁移规则见[下文](#ir-v8-migration)。
Rust 库接口：`Circuit::new(...)` 和无状态的 `Circuit::solve(inputs)`。
独立 Rust 进程也校验 IR，不能依赖 Python 已验证输入。

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块依赖 IR 和表达式校验，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份沿用 v2；当前开发分支表达式、事件与算子使用 IR v16，序列化迁移规则见下文。

当前用 JSON 进程接口使 IR 易于检查，避免先复制旧的复杂 FFI。
已有性能检查只覆盖对应历史检查点的 Rust 库内工作点求解，未测 Python/JSON 进程接口的端到端吞吐量。

## 本地求解性能检查

[static_solver.rs](rust_core/benches/static_solver.rs) 提供 Rust 库内构造解核对和局部计时：

```sh
cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=chain-64 EVAS_BENCH_SAMPLES=1024 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
```

基准的准备/首次/重复求解边界、稠密/稀疏分流及局限统一见[数值手册](docs/NUMERICS.md#稀疏分支与性能边界)。
旧 0.3.1/0.3.2 的重复求解比较保留在[固定历史记录](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#本地求解性能检查)，
不代表当前版本、首次求解、瞬态或跨后端速度。

## 实现范围

- 一个源文件一个 module，标量端口及内部 `electrical` 节点，显式方向声明。
- 文件前部可使用标准 `constants.vams` / `disciplines.vams` include 拼写。
  本切片把它们视为内建前导声明，不搜索外部文件；当前只识别有限常量 `` `M_PI``，不提供通用宏处理。
- `parameter real` 默认值、实例覆盖以及参数依赖，有限实数与 SI 后缀。
- 一个 `analog begin ... end`，含无条件 `V(p)` / `V(p,n)` 贡献，以及下述限定事件块。
- 表达式支持括号、单目正负、加减、乘法及非零常数分母。
- `pow(base, exponent)` 的指数须在实例绑定后为 **1–32 的整数常数**，支持负数、零和正数底数；
  该界限是本内核的实现范围，不声称覆盖完整 `pow`。变量、分数、零和负指数仍拒绝。
  数学函数的语言来源见 [LRM 2.4 数学函数表](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)。
- manifest 提供平面实例和端口到全局网络的显式映射。内部节点使用实例私有名称。
- 全局 `0` 为固定地；其他驱动节点由调用者显式指定。每个样本提供完整驱动值。

瞬态贡献可使用 `idt(direct_affine_input, constant_ic)`，对连续 PWL 直接输入分段解析积分。
另支持 `idt(direct_affine_input, constant_ic, state_reset)`；reset 限同实例状态的仿射表达式，
须认证为零/非零，且不形成结构复位反馈环。每个调用点独立，历史误差参与电压验收。
IR16 开发分支增加仿射内部节点、线性嵌套和积分电压反馈；状态输入、联合网络 reset 和非线性动态反馈仍拒绝。
积分输出的受限连续 cross、直接 PWL 的 ddt、完整分子的 1–8 阶 proper 滤波见[连续动态说明](docs/CONTINUOUS.md)；
数学与限制见[算子手册](docs/OPERATORS.md#idt)，历史复位对照见[验证记录](../experiments/pr14-pr15-validation/RESULTS.md#idt-reset-merge-validation)。

事件体条件的精度和支持边界见[事件手册](docs/EVENTS.md#event-conditions)。
另支持无事件/初始化的顺序局部 `real` 赋值和输入驱动 `if/else`；瞬态限分段仿射叶子，
详见[普通 analog 条件契约](validation/ANALOG_CONDITIONS_CONTRACT.md)。无条件局部算子别名捕获调用处表达式，每个调用保留独立身份。
另支持直接连续 PWL 的一阶 `laplace_nd(u, '{b0}, '{d0,d1})`、显式正 modulus 的
`idtmod`，以及直接仿射输入或单个早期算子仿射值的受限 `sin`；数学、误差和组合限制见
[算子手册](docs/OPERATORS.md#laplace_nd)。无状态、无事件、无历史算子时可逐点解多项式瞬态，见
[精度契约](validation/NONLINEAR_TRANSIENT_CONTRACT.md)。
仍拒绝超出所列范围的过程赋值、条件、循环、层次实例、通用数组、命名支路、电流贡献、
其他数学函数、未列明的事件/动态算子、其他预处理指令、参数范围和未知语法。
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

当前开发分支使用 IR v16，增加 ddt、连续动态网络与动态 guard，延续 v11 的 idt 复位与逐条贡献契约；每条贡献的 RHS 是带 `op` 标签的表达式，不含“直接写节点”指令。
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
前端与内核须配套使用，IR15 main 内核不能消费此开发分支的 IR16。

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

## 求解和错误

方程、Newton 验收、精度控制、稠密/稀疏求解与失败分类统一维护在[数值手册](docs/NUMERICS.md)。

## PWL 与事件的执行契约

PWL/cross、事件体条件、同块顺序赋值、同刻联立与提交/回退见[事件手册](docs/EVENTS.md)。

### 固定 timer

参数、名义日程、边界顺序与定位认证见[固定 timer](docs/EVENTS.md#固定-timer)；示例为 [timer_counter.json](examples/timer_counter.json)。

## 固定 slew 执行契约

限速、追赶交点、历史误差与拒绝边界见[slew](docs/OPERATORS.md#slew)。

## 扩展与验证边界

[独立验证集](validation/README.md)维护需求、答案和判据；完整观察资格与未见确认集仍待补。
新能力先建立独立契约，再更新相应模块、手册和能力表。单算子通过不证明任意组合正确。

### 固定 absdelay

历史查询、局部延迟、误差传播与拒绝边界见[absdelay](docs/OPERATORS.md#absdelay)；示例为 [absdelay.json](examples/absdelay.json)。

## transition 波形算子

有限边沿、延迟队列、中断沿及同刻求解见[transition](docs/OPERATORS.md#transition)；示例为 [transition_pulse.json](examples/transition_pulse.json)。
