# EVAS

当前实现为 **EVAS 0.2.0 静态仿射内核，IR v2**，尚未替换旧 EVAS 0.8.7。
从限定的 Verilog-A 源码生成贡献方程，再由 Rust 同时求解节点电压，允许自反馈与实例间反馈。
每个输入样本独立求一个静态工作点；没有物理时间推进或历史状态。

长期范围是声明的电压域行为及交互，与 Spectre 对标，并为 VABench 的开放复现及
agentic eval 提供后端。当前支持由语法和语义决定，运行时不识别验证集或模型名称。

## 构建与运行

需要 Python 3.10+ 和 Rust/Cargo。以下命令在仓库根目录运行：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas compile evas/examples/static_sum.json
PYTHONPATH=evas/src python3 -m evas solve evas/examples/static_sum.json --kernel evas/rust_core/target/debug/evas-kernel
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
PYTHONPATH=evas/src python3 evas/tests/run_static_regression.py --kernel evas/rust_core/target/debug/evas-kernel --output runs/evas-static-replay
```

回放命令要求新的输出目录，读取原 31 条件的 VA、输入和独立判据。
当前可编译其中 9 条（V2 四条、V7 线性三条、S1 两条），其余 22 条明确拒绝。
两档对应 4,001／40,001 点的静态采样网格和残差设置，不是瞬态仿真或 DVS 正式资格。

## 回归证据

提交 `b877e5b` 的检查包含 33 项 unittest 方法、锁定依赖的离线 Rust 构建、
warnings-as-errors 的 all-targets 检查及格式检查，均通过。
9 条件 × 两档 = 18 组，共 396,018 个静态点满足原独立判据；18 份波形 CSV
与上一检查点逐字节一致，22 条拒绝诊断及引用的 20 个验证源码/判据文件身份保持一致。
33 是程序测试方法数，31 是独立验证条件数，两者不相加。

完整历史、执行身份和 review 边界保留在
[检查点记录](https://github.com/BucketSran/vaEVAS/blob/b877e5b/evas/REVIEW.md)及
[PR #2](https://github.com/BucketSran/vaEVAS/pull/2)。上述回归没有在 thu-sui 重跑四后端，
没有取得动态/事件/非线性支持、性能排名或完整 DVS 资格。

## 模块与接口

| 模块 | 当前文件 | 唯一职责 |
| --- | --- | --- |
| 语法解析 | `src/evas/syntax.py` | 完整消费 token，生成带源码位置的语法树 |
| 语义绑定 | `src/evas/frontend.py` | 绑定参数/节点，将仿射表达式转换为贡献 IR |
| IR | `src/evas/ir.py`、`rust_core/src/ir.rs` | Python/Rust 之间带版本和源码位置的数据契约 |
| 方程组装 | `rust_core/src/assembly.rs` | 校验 IR 与驱动配置，累加支路贡献，生成方程系数及节点分区 |
| 工作点求解 | `rust_core/src/solver.rs` | 代入每个样本的驱动值，求解未知电压，验收原方程残差 |
| 线性代数 | `rust_core/src/linear.rs` | 行缩放、选主元与稠密消元 |
| 进程接口 | `src/evas/runtime.py`、Rust `main.rs` | 一个批次一次 JSON 请求，无 Python 求值回调 |
| 用户入口 | `src/evas/__main__.py` | 读取显式平面电路 manifest，输出 IR 或结果 |

Python 的公开接口：`compile_sources(sources, instances) -> Program`，
`solve(program, driven, samples, kernel=...) -> result`。
Rust 库接口：`Circuit::new(...)` 和无状态的 `Circuit::solve(inputs)`。
独立 Rust 进程也校验 IR，不能依赖 Python 已验证输入。

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块只依赖 IR，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份使用 IR v2，序列化迁移规则见下文。

当前用 JSON 进程接口使 IR 易于检查，避免先复制旧的复杂 FFI。
这不是最终吞吐量方案；未做运行速度比较。

## 实现范围

- 一个源文件一个 module，标量端口及内部 `electrical` 节点，显式方向声明。
- 文件前部可使用标准 `constants.vams` / `disciplines.vams` include 拼写。
  本切片把它们视为内建电气前导声明，不搜索外部文件；不提供常量宏展开。
- `parameter real` 默认值、实例覆盖以及参数依赖，有限实数与 SI 后缀。
- 一个 `analog begin ... end`，只含无条件 `V(p)` / `V(p,n)` 贡献。
- 表达式支持括号、单目正负、加减、常数乘除；拒绝非线性乘法与变量分母。
- manifest 提供平面实例和端口到全局网络的显式映射。内部节点使用实例私有名称。
- 全局 `0` 为固定地；其他驱动节点由调用者显式指定。每个样本提供完整驱动值。

当前拒绝过程变量/赋值、条件、循环、层次实例、数组、命名支路、电流贡献、
数学函数调用、事件、动态算子、其他预处理指令、参数范围和未知语法。
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

IR v2 保留每条贡献，其 RHS 是常数加节点系数，不含“直接写节点”指令。
每条贡献有源码文件、行列、实例以及本地支路身份。

`branch` 从 v1 的逗号拼接字符串变为结构化对象，例如：

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

### v1 → v2 迁移

Python 包与 Rust 内核一起升级到 0.2.0；Program 和成功 Response 的
`schema_version` 均为 2。Python 适配器拒绝其他响应版本。
内核 CLI 在解码贡献字段前检查整数版本号：v1 或未知版本返回
`unsupported_ir_version`；缺失/错误类型及 v2 格式错误返回 `invalid_request`。
Rust 库的构造入口也检查版本。

已有 v1 JSON 应从原始 VA 和 manifest 重新编译；不提供自动猜测或字符串拆分迁移。
旧归档保持原样，复现时使用旧提交对应的前端和内核。旧内核也不能执行 v2 请求。

## 求解和错误

当前采用行缩放、部分主元的稠密消元，适用于本批小规模回归。
所有非驱动节点同时作为未知量；没有 SCC 优化、稀疏求解或数值条件数保证。
冗余方程在最终残差检查中保留；欠定或数值秩不足时明确失败。

解算后重新计算每条组装前物理支路关系的左右两侧，要求：

`abs(lhs-rhs) <= absolute + relative * max(abs(lhs), abs(rhs))`

两项容差均须有限，absolute > 0、relative >= 0。
残差是约束满足度检查，不是任意病态问题的前向误差保证。
每个成功样本返回最大伏特残差及其相对容差比例。

错误区分编译拒绝、IR/输入错误、数值奇异、非有限运算、残差超限；
方程错误带源码/实例信息，运行期样本错误带从 0 开始的样本下标。
任何样本失败都使整个请求失败，不输出部分成功波形。

## 扩展与验证边界

新语义沿用同一套 IR 和执行内核。事件与动态算子需要明确已接受状态、候选状态以及
提交/撤销规则；非线性反馈需要独立的残差与收敛契约。当前没有预建这些框架。
代码按语法、绑定、组装与数值求解分工；具体扩展先建立独立契约，再修改对应模块。

[独立验证集](validation/README.md) 的需求、答案和判据独立于 EVAS 实现。
现有 31 条已参与诊断，属于开发回归；最终评估需另设事先冻结的确认集。
[四后端基线](../experiments/dvs2-four-backend-validation/README.md) 测的是旧 EVAS 0.8.7，
不能与本静态子集直接比较总分。应用任务回归也不能代替语义正确性验证。

本前端和内核为新实现。旧源码审查来源及其构建身份限制见
[诊断记录](../experiments/dvs2-four-backend-validation/DIAGNOSIS.md)；旧仓库及部署镜像保持原样。
阶段设计和 review 讨论留在提交及 PR 历史，本页维护当前可用接口与契约。
