# EVAS

当前实现为 **EVAS 0.4.0，IR v4**：静态多项式求解，以及限定 PWL/仿射网络的 `cross` 事件执行。尚未替换旧 EVAS 0.8.7。
从限定的 Verilog-A 源码生成贡献方程，再由 Rust 同时求解节点电压，允许自反馈与实例间反馈。
`solve` 的每个样本独立求静态工作点；`transient` 沿物理时间推进，保存实例私有状态。两种入口明确区分。

长期范围是声明的电压域行为及交互，与 Spectre 对标，并为 VABench 的开放复现及
agentic eval 提供后端。当前支持由语法和语义决定，运行时不识别验证集或模型名称。

## 构建与运行

需要 Python 3.10+ 和 Rust/Cargo。以下命令在仓库根目录运行：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas compile evas/examples/static_sum.json
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_sum.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_nonlinear.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m evas transient evas/examples/cross_counter.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
cargo test --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 evas/tests/run_static_regression.py --kernel evas/rust_core/target/debug/evas-kernel --output runs/evas-static-replay
```

回放命令要求新的输出目录，读取原 31 条件的 VA、输入和独立判据。
当前可编译其中 11 条（V2 四条、V7 线性三条、V7 非线性两条、S1 两条），其余 20 条明确拒绝。
两档对应 4,001／40,001 点的静态采样网格和残差设置，不是瞬态仿真或 DVS 正式资格。

## 回归证据

当前检查包含 **61 项 Python unittest 方法、4 项 Rust 测试**，以及锁定依赖的
离线构建、warnings-as-errors 的 all-targets 检查和格式检查，均通过。
其中新增 18 项 Python 方法覆盖事件时间/方向/次数、时移/斜率/步长变化、初始化、
内部节点触发、实例隔离、同时事件、相切及拒绝边界；新增 3 项 Rust 测试覆盖
丢弃候选后重试、事件后残差失败和整数溢出时状态不提交。它们不是跨后端资格测试。

原 11 条件 × 两档 = 22 组，共 **484,022 个静态点**满足原独立判据；
22 份波形 CSV 与 0.3.0 归档逐字节一致。其余 20 条仍明确拒绝。
新增无 `transition` 的计数器示例产生约 0.5、1.5、2.5 µs 的三次事件，最终状态为
上升沿 2 次、下降沿 1 次。这些开发探针不替换原 E1，也不改变原 31 条件的分母或支持数量。

程序测试方法数与独立验证条件数分开报告。本轮新增控制属于 EVAS 开发回归，
没有增加原 31 条件的跨后端分母，也不称为未见确认集。
旧检查点的执行身份与 review 记录见
[历史记录](https://github.com/BucketSran/vaEVAS/blob/b877e5b/evas/REVIEW.md)，
初始内核审查见已合并的 [PR #2](https://github.com/BucketSran/vaEVAS/pull/2)；后续阶段的范围、验证摘要与证据哈希记录在各自提交和 PR 中。
本轮没有在 thu-sui 重跑四后端；事件结论仅限下述实现范围和开发测试，没有取得完整瞬态资格、通用非线性收敛或性能优势结论。

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
| 线性代数 | `rust_core/src/linear.rs` | 行缩放、选主元与稠密消元 |
| 事件语义 | `rust_core/src/events.rs` | 校验状态/事件身份及依赖，将状态代入方程，准备事件块的状态更新 |
| 连续输入与根 | `rust_core/src/pwl.rs` | 校验连续 PWL、求值、识别方向及区间内孤立根 |
| 时间推进 | `rust_core/src/transient.rs` | 事件定位、候选试算、原子提交、输出实际接受的事件记录 |
| 进程接口 | `src/evas/runtime.py`、Rust `main.rs` | 一个批次一次 JSON 请求，无 Python 求值回调 |
| 用户入口 | `src/evas/__main__.py` | 读取显式平面电路 manifest，输出 IR 或结果 |

Python 的公开接口：`compile_sources(sources, instances) -> Program`，
`solve(program, driven, samples, kernel=...) -> result`，以及
`transient(program, sources, output_times, stop=..., max_step=..., kernel=...) -> result`。
Rust 库接口：`Circuit::new(...)` 和无状态的 `Circuit::solve(inputs)`。
独立 Rust 进程也校验 IR，不能依赖 Python 已验证输入。

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块依赖 IR 和表达式校验，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份沿用 v2；表达式和事件使用 IR v4，序列化迁移规则见下文。

当前用 JSON 进程接口使 IR 易于检查，避免先复制旧的复杂 FFI。
这不是最终吞吐量方案；未做运行速度比较。

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

当前拒绝事件块之外的过程赋值、条件、循环、层次实例、数组、命名支路、电流贡献、
`pow` 之外的数学函数、未列明的事件、动态算子、其他预处理指令、参数范围和未知语法。
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

IR v4 保留每条贡献，其 RHS 是带 `op` 标签的表达式，不含“直接写节点”指令。
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

### v1/v2/v3 → v4 迁移

Python 包与 Rust 内核一起升级到 0.4.0；Program 和成功 Response 的
`schema_version` 均为 4。Python 适配器拒绝其他响应版本。
内核 CLI 在解码贡献字段前检查整数版本号：v1/v2/v3 或未知版本返回
`unsupported_ir_version`；缺失/错误类型及 v4 格式错误返回 `invalid_request`。
Rust 库的构造入口也检查版本。

已有 v1/v2/v3 JSON 应从原始 VA 和 manifest 重新编译；不提供自动猜测或字符串拆分迁移。
旧归档保持原样，复现时使用旧提交对应的前端和内核。旧内核也不能执行 v4 请求。不要只修改版本号：v3 引入表达式标签，v4 又引入实例状态和事件。
`Program.states/events` 为空时保持静态语义；省略这两个字段也只表示空列表，不推断任何事件。
`state` 表达式保存状态索引，状态含实例身份、名称、类型及初始化常数；事件含 guard、方向、
两项容差、有序赋值和源码位置。Rust 独立验证这些字段；静态入口拒绝含状态/事件的程序。

## 求解和错误

纯仿射电路继续采用行缩放、部分主元的稠密消元，保持原数值路径。
含多项式项时使用同一组装后的支路约束与同一个线性代数模块计算 Newton 更新。
所有非驱动节点同时作为未知量；没有 SCC 优化、稀疏求解或数值条件数保证。
冗余方程在残差检查中保留；欠定或数值秩不足时明确失败。

非线性求解每个样本从未知节点全零开始，驱动电压固定，不读取上一样本作为初猜。
解析链式法则生成 Jacobian；最多 80 次更新，每次最多 32 次试步，失败则步长减半，使用固定当前
残差尺度的充分下降检查。试步溢出时缩步；初始求值非有限、局部 Jacobian 奇异、
线搜索失败或预算耗尽均显式报错。已达到残差目标时也检查局部秩，避免接受悬空未知量。

解算后重新计算每条组装前物理支路关系的左右两侧，要求：

`abs(lhs-rhs) <= absolute + relative * max(abs(lhs), abs(rhs))`

两项容差均须有限，absolute > 0、relative >= 0。
残差是约束满足度检查，不是任意病态问题的前向误差保证。
当前算法不证明全局唯一性，也不保证从零初猜收敛到所有存在的根；多解分支选择、
奇异根、延续法及通用非线性网络鲁棒性不在本阶段验收范围。
每个成功样本返回最大伏特残差及其相对容差比例。

错误区分编译拒绝、IR/输入错误、线性奇异、`singular_jacobian`、`nonconvergence`、
非有限运算与残差超限；
方程错误带源码/实例信息，运行期样本错误带从 0 开始的样本下标。
任何样本失败都使整个请求失败，不输出部分成功波形。

## PWL 与 cross 的执行契约

这是限定实现范围，不是完整 Verilog-A 事件支持。语言依据见
[LRM 2.4](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf) 和
[事件语句参考](https://verilogams.org/refman/modules/analog-procedural/timing.html)。

- 声明标量 `integer` / `real` 状态，每个状态必须恰有一次 `@(initial_step)` 常数赋值，
  可以引用有效实例参数；暂不接受依赖电压或其他状态的初始化。初始化常数在绑定时确定，
  Rust 在 t=0 的首次求解前安装一次。初始高电平、初始零值的离开本身不产生 `cross`。
- `@(cross(g[, direction[, ttol[, tol]]]))` 接受空语句或顺序赋值块。方向为 -1/0/+1，默认 0；
  两项容差必须为正的有限实例常数，默认分别为 1 ps 和 1e-9 表达式单位。不支持 enable 或事件 `or`。
- 瞬态贡献、guard、赋值表达式必须对电压和状态联合仿射；静态多项式能力仍只适用于 `solve`。
  整数状态采用精确 signed 32-bit 范围，仅接受整数常数/整数状态运算，超范围报错，不模拟溢出或隐含取整。
  real 状态可以在事件时采样仿射电压表达式。
- 每个状态只能由一个 cross 块写入；同块语句依次看到自己的更新。
  事件块不能直接读取其他 cross 块写入的状态。同一可表示时刻的多个事件读取同一份事件前电压和状态，
  各自准备更新，再共同求解事件后电压。容差不被用来任意合并相邻事件。
- guard 不得直接依赖状态，也不能通过电压方程间接依赖状态。Rust 用方程连通性保守检查，
  排除固定驱动和地；即使某种代数抵消可能消除依赖，也可能明确拒绝，避免依赖浮点阈值漏检反馈。
- 每个驱动用连续 PWL 点列描述，从 t=0 开始、时间严格递增且覆盖 stop；不接受重复时间造成的跳变。
  `output_times` 是 [0,stop] 内严格递增的有限观测时刻，`stop/max_step` 均为正且有限。
  观测时刻会实际求解；若恰逢接受的事件时刻，返回事件后电压。事件不必落在输出网格上。

通过上述限制，固定状态下的方程系数不变，输入每个分段内的节点电压和 guard 都是时间的仿射函数。
内核在所有输入断点上求解，解析定位孤立根，再在根处重新求解核验。guard 的状态独立性允许提前生成事件日程，
它不读取测试集答案。用于定位的初始化状态冻结试算也必须可解；不能完成时直接报告错误。
原始根若因浮点舍入落在过零前一侧，最多尝试 128 个后继浮点时间，在所在区间内寻找方向正确且满足
两项容差的点；不可表示或容差不满足则返回 `event_resolution`。不使用表达式容差作为忽略小信号的死区。
这是双精度计算和所列测试的保证，不是任意病态电路的严格实数根界限证明。

过零恰在断点时只执行一次；相切但两侧同号不执行。零值平台以及 stop 恰为零、缺少右侧信息的情况
返回 `unsupported_cross`，暂不解释成某一种边沿。仿真最多接受 1,000,000 步；不能继续推进可表示时间或
超过步数预算时显式失败。

运行时持有一份已接受状态及其已组装电路。普通时间点复用该电路；状态变化才重新绑定/组装。
先试算候选时间，若有更早的事件就丢弃该候选；随后在事件时刻准备状态、检查范围、重新解算电压并检查
原支路残差。全部成功后才同时提交时间、状态、电路、事件游标与记录。
失败或丢弃的候选不会消耗事件或增加计数器；请求任何一步失败均不返回部分成功结果。
返回的 `transient` 字段含观测时间/状态、实际接受的 cross 记录（时间、事件序号、源码、guard 值及前后状态）、
接受步数和因更早事件而丢弃的候选数。记录中的前后状态是同一时刻整批事件的快照。

后续需要单独扩展：`transition`、timer、条件控制/复合事件、状态反馈 guard 的同刻迭代、
动态算子和非线性轨迹上的通用根定位。当前计数器直接输出理想电压阶跃，未实现平滑边沿。

## 扩展与验证边界

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
