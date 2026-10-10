# EVAS：电压域 Verilog-A 仿真器

模型支持范围及已有对照证据见[四后端支持范围](docs/COMPARISON.md)。

EVAS 面向 Verilog-A 行为模型的开发与验证。首要目标是提供开源、可审查的电压域仿真环境，
让使用者不依赖商业仿真器也能运行和验证目标模型，为 benchmark 提供开源复现路径。
EVAS 有独立的使用者、验收标准和交付成果；速度优化须保持模型语义和误差要求。

用户可以先用 EVAS 迭代模型，再用同一份 VA 验证 Spectre 兼容性，最后与实际器件网表共同仿真。
开源复现是建设目标，覆盖程度以具名版本和具体模型的对照证据为准。
benchmark 遇到 EVAS 能力缺口时，可以继续使用已校准的 Spectre 验收；
EVAS 按受影响的任务类别、工程使用频率与实现成本选择扩展，不要求题目等待全部能力补齐。

EVAS 把限定范围内的 Verilog-A 电压关系编译为方程，联立求解节点电压。
它适合描述理想电压域行为，例如增益、限幅、采样、事件计数和连续时间算子。
它不包含晶体管器件模型、电流/电荷方程或完整 SPICE 网表求解。

限定求解范围，为专门的算法和实现优化提供了空间；实际速度仍受模型规模、
稀疏性、事件密度和精度要求影响。性能结论需要绑定具体模型、误差标准与测量环境。
优化不能通过改变模型语义、跳过真实事件或放宽验收要求来获得速度收益。

前端使用 Python 解析、绑定并生成 IR，Rust 内核完成求解与时间推进。
同一支路的多条贡献会相加；程序赋值则保留顺序语义。
瞬态试算从已接受历史出发，电压、状态和误差检查通过后一起提交。

当前开发基线和历史版本见[版本记录](docs/UPDATE.md#baseline-20261009)。

<a id="model-handoff"></a>

## 与电路仿真配合

模型移交以 `.va` 源码、实例参数、端口定义、初始条件和验证用例为基础。
模型在 EVAS 中通过后，先在 Spectre 中运行相同源码与等价刺激，再接入器件级网表。
具体负载、驱动和反馈连接由集成测试台声明，交给 Spectre 共同求解。

这三个层次分别验收：

| 层次 | 检查内容 |
| --- | --- |
| 数学正确性 | 根据规格和语言语义建立独立答案，检查电压关系、状态演化与事件 |
| 后端兼容性 | 同一模型在 EVAS 与 Spectre 中，事件次数、顺序、时刻和波形满足共同判据 |
| 网表集成 | 接入实际电路后，初始化、负载、反馈和接口假设仍符合模型规格 |

两个后端可以采用不同算法和内部时间步；比较使用事先约定的输出误差与事件要求。
相同名称的容差参数不保证相同的输出误差。发现差异时，分别检查模型写法、
语言语义、数值设置和求解器实现；不能仅以任一后端的结果作为正确答案。
EVAS 通过独立测试，也不能直接标记为已通过 Spectre 兼容性验证。

电压域模型还需要说明接口假设。例如，理想电压输出没有自动包含真实的输出阻抗、
限流和负载效应；这些行为需在模型或外围电路中显式表达，并在集成阶段验证。
预先计算的波形适合单向激励。存在电路反馈时，需要使用能响应输入变化的行为模型。

当前的[测试台读取](#spectre-testbench)和[后端对照](../experiments/backends/dvs2-spectre-validation/README.md)
是这条工作流的已有基础。兼容性证据限于已测模型、配置和仿真器版本；
通用的自动移交与 EVAS/Spectre 运行时同步接口尚未实现。

## 查询实际包与内核身份

`PYTHONPATH=evas/src python3 -m evas version --json --kernel /path/to/evas-kernel`
查询所选二进制的身份、SHA-256 与 IR 版本；省略 `--kernel` 时只查询 Python 包。
内核可直接运行 `evas-kernel --version --json`，无需 manifest 或标准输入。
缺少构建来源和独立请求协议元数据时明确返回 null；IR 匹配不等于全部运行兼容。
字段及失败行为见[身份接口](docs/reference/identity.md)。

## 仅编译预检

```sh
PYTHONPATH=evas/src python3 -m evas lint evas/examples/01-static-gain/sim.json
```

`lint` 检查 manifest 编译字段、源文件读取、参数绑定、受支持源码编译及 IR 资源预算，
输出 JSON，不查找或启动内核，并明确拒绝 `--kernel` / `--timeout` 执行选项。`lint_passed` 不检查数值请求内容、动态组合支持、
数值精度或外部仿真器兼容性。例如可编译的 timer/多项式 DAE 组合仍可能在瞬态执行时拒绝。
诊断只为已登记的 manifest/source I/O、参数依赖/覆盖和资源来源补充分类；
未登记的 code/kind 保留原消息、位置与额外字段，类别为 `unknown`，不按前缀或消息猜测。
接口与来源盘点边界见[诊断说明](docs/reference/diagnostics.md)。

## 安装配套发行包

平台 wheel 可携带独立 Rust 内核，安装后 `evas-rebuild solve MANIFEST` 无需 PYTHONPATH 或显式内核。
默认选择校验包内核身份；显式 `--kernel` 保持可用，失败不回退。
构建、安装、平台证据边界和源码方式见[安装合同](docs/reference/install.md)。尚未发布到公共索引或打 tag。

有限标量 `case/default` 的支持范围、资源预算与拒绝边界见 [case 契约](validation/CASE_STATEMENTS_CONTRACT.md)。

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
[examples/](examples/) 从静态求解、瞬态历史讲到事件；第 4 课展示当前分支的事件与积分组合候选，
每课提供模型、运行清单与期望输出；覆盖各条仿真能力路径的最小冒烟集
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

当前准入下，冻结的 `absdelay`、`timer_counter` 原 VA 缺少 discipline 声明，
`cross_counter` 原 VA 含非法小数拼写，直接按这些 manifest 重编译会拒绝。
原文件与历史结果保留；可运行的显式版本见
[smoke-admission-v1 successors](tests/fixtures/smoke-admission-v1/README.md)。
`idt`、`transition_pulse` 和 `static_nonlinear` 的原 manifest 仍可编译。
CLI 的 `solve`/`transient` 会读取 manifest 的 VA 并重新编译；
API 运行已有 `Program` 不重复源码准入，但仍须满足当前 IR/内核版本契约。

## 精度与结果解释

支持独立于输出网格的 `strobetimes` 和周期 strobe 控制，见[强制求解时刻](docs/reference/strobe.md)。
`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（默认 `1e-12 V`）
与 `reltol`（默认 `1e-10`，无量纲）。这两个数字是求解/验收设置，
不能直接解释为所有输出都具有同样的全时域精度。
静态 Newton 检查原方程残差；瞬态还要考虑输入、历史、采样及事件时刻的误差和网络放大。
各控制项和失败处理见[精度控制](docs/math/solving.md#当前精度控制怎么用)，具体数值方法见同章。
瞬态响应可选保存实际控制值、逐行来源和已有节点认证区间，见[观察证据接口](docs/reference/observation-evidence.md)。缺失区间保持未知，这些字段不自动授予外部观察资格。

<a id="spectre-testbench"></a>

### Spectre 风格电压测试台

`simulate` 将受限 `.scs` 输入转换为已有的实例、PWL 和瞬态请求，再交给同一 Rust 内核：

```sh
PYTHONPATH=evas/src python3 -m evas simulate evas/examples/01-static-gain/tb.scs --kernel evas/rust_core/target/debug/evas-kernel
```

[示例测试台](examples/01-static-gain/tb.scs)的独立答案是 `out = 2*u - 0.125 V`。
API 为 `evas.scs.load_scs(path)`（检查测试台并返回 manifest 和模型文本），
以及 `simulate_scs(path, kernel=...)`（编译并运行）。`load_scs` 成功只说明已完成输入适配，
不代表 IR 编译、动态组合或数值验收成功。

| 输入 | 当前接受范围 |
| --- | --- |
| 模型与连接 | `ahdl_include "file.va"`；按 VA 声明顺序展开静态向量后逐位连接的标量节点列表；常量参数覆盖；`global 0` |
| 数字 | 有限十进制、科学计数和单字母 SI 后缀 `T G M k K m u n p f a`；可引用先前 `parameters` 语句的常量 |
| `vsource` | 一端接地；`dc`；从零开始、时间严格递增的 `wave=[time value ...]`；显式 `delay/rise/width/fall/period/val0/val1` 的线性 pulse |
| 瞬态 | 一条 `tran tran stop=... maxstep=...`，两项必须显式指定且为正；观察点取 `0`、小于 stop 的 `k*maxstep` 和 stop；可另给 [strobe 五项控制](docs/reference/strobe.md)，不改变常规观察网格 |
| 精度 | `options reltol=... vabstol=...`，映射到现有 EVAS 设置；未指定项使用 EVAS 默认值，不采用 Spectre 默认值 |
| 输出 | `save` 选择标量端口节点；`saved` 输出所选列，原 `solutions` 保留完整求解响应 |

输入允许 `//` 注释、反斜杠续行和跨行括号。所有字段必须被消费。
未知 options、`iabstol`、`errpreset`、sine、理想跳变、浮动源、R/C/I 器件、
子电路指令、电流探针、总线名/范围/拼接/切片等连接语法均明确拒绝；不把它们当作可忽略的文本。
VA 的自定义 include 仍使用显式 source 清单；适配器只加载 `ahdl_include` 列出的文件。
重复源、重复设置、非法源时刻和未知 save 节点在运行前拒绝。

静态向量端口按每个实例的有效参数展开，索引按声明方向依次连接。
例如 `input [1:0] u; output [0:1] y;` 的 `DUT (a b c d) bus`
对应 `u[1]=a,u[0]=b,y[0]=c,y[1]=d`；列表长度必须与展开后的端口数相同。
参数宽度、负/非零索引和单元素范围复用已有 VA 绑定规则。
见[输入契约与 Spectre 准入证据](validation/SCS_VECTOR_CONTRACT.md)及
[公共入口回归](tests/test_scs_vectors.py)。

DC 和 PWL 保留输入数值与所有拐点。PWL 末点之后保持最后的值。
pulse 的第 k 次起点为 `d+kP`，四个拐点为 `d+kP`、`d+kP+r`、
`d+kP+r+w`、`d+kP+r+w+f`；要求 `r,f,P>0`、`d,w>=0`、`r+w+f<=P`。
拐点由已解析的 binary64 参数用有理数计算；非恒定 pulse 的拐点必须能精确表示为 binary64。
不能精确表示或时刻分辨率不能表示边沿时明确拒绝，等待源时刻不确定性进入全网络误差链。
这会拒绝部分常用十进制时间组合；不能用很小的电压方程残差掩盖源时刻舍入。
输出中的 `testbench.pulse_corner_rounding_seconds` 保留源构造的检查结果。
这不是通过输出网格采样近似 pulse；改变 maxstep 不改变源拐点。
网表 token、输出点和每个 pulse 点均有 100000 的资源上限。

`testbench` 同时记录测试台/模型 SHA256、生效容差及观察网格约定。
格式适配不等于完整 Spectre 兼容或对照实验；独立答案与 manifest 等价性由
[test_scs.py](tests/test_scs.py)检查。网表解析与源构造分别位于
[scs.py](src/evas/scs.py)和[scs_sources.py](src/evas/scs_sources.py)。

旧 IR 1–17 必须从原始 VA/manifest 重新编译；前端与内核需要配套。
批量工具和兼容性规则见[IR 版本与迁移](#ir-v8-migration)。

## 验证与开发

[独立验证集](validation/README.md)维护模型契约、数学答案和判据。
[当前执行证据](../experiments/runs/capability-completion/README.md)记录原 31 条件
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

<a id="实现范围"></a>

语法和参数的详细约束见[模型编译](docs/reference/frontend-admission.md#模型编译)。

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
同时缓存子图的计算结果；不会为了估算大小而先复制整个表达式树。纯函数的编译期
校验义务按同一展开中的 AST 身份合并；义务不加入计算值替换或序列化的展开成本，
函数赋值 RHS 和返回值仍检查原深度/大小上限。源 token 总数限 100,000，函数调用嵌套
限 64；函数调用、表达式下降与条件体嵌套共同累计到 80 层展开深度预算，
避免分别合规的嵌套相乘使编译器递归溢出；不另设累计校验图上限。
超限时返回带源码位置的 `CompileError`。合法但过大的模型也可能被拒绝，
包括旧版本偶尔能处理的长表达式。使用 IR18，不通过重关联算式或消去依赖绕过预算；
更大的模型需要后续共享表达式 IR 或其他有独立验证的方案。

`solve` / `transient` 的 `timeout` 默认 **300 秒**，只限制内核进程执行时间，
不包含 Python 编译与序列化。API 可传正的有限秒数，或用 `timeout=None` 关闭上限。
CLI 使用 `--timeout 600` 调整；时间超限会终止并回收内核子进程，报告 `kernel_timeout`。
仿真时间 `stop` 与这个墙钟时间上限是两个不同设置。

CLI 的内核失败在 stderr 输出 JSON，保留 `kind`、`message` 和存在时的 `sample`；
成功结果仍输出到 stdout。输入/编译错误也输出带 code/阶段的 JSON，错误退出码均为 2。
适配器验证返回结果的身份、行数、电压/状态维度及有限数值；坏响应为 `invalid_response`，
无法启动进程或不合格式的进程错误为 `kernel_process`。
这些检查保护调用边界，不代替内核的电压精度验收。

## 模块与接口

仅编译预检接口为 `evas.lint.lint_manifest(path) -> dict`。
Python 的编译与求解接口：`compile_sources(sources, instances) -> Program`，
`solve(program, driven, samples, kernel=...) -> result`，以及
`transient(program, sources, output_times, stop=..., max_step=..., kernel=...) -> result`。
支持独立于输出网格的 `strobetimes` 和周期 strobe 控制，见[强制求解时刻](docs/reference/strobe.md)。
`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（伏特，默认 `1e-12`）与
`reltol`（无量纲，默认 `1e-10`），例如 `solve(..., vabstol=1e-9, reltol=1e-6)`。
保留 `absolute` / `relative` 作为对应旧名称；同一容差不能同时提供新旧名称。
本分支的非线性 Taylor/DAE 路径将节点容差用于候选细化，并保留最终前向电压误差验收。
`max_step` 同时限制其内部试步；线性/PWL 解析路径保持解析传播。观察网格不定义积分历史。
极小步长或无法认证的累计包围会明确失败，资源上限与数学说明见
[非线性精度控制](docs/math/continuous.md#多项式非线性积分与误差证明)。
当前实现 Python 前端与 Rust 内核使用 IR v18；版本迁移规则见[下文](#ir-v8-migration)。

Rust 库接口：`Circuit::new(...)` 和无状态的 `Circuit::solve(inputs)`。
独立 Rust 进程也校验 IR，不能依赖 Python 已验证输入。

静态批量求解默认串行。设置 `EVAS_STATIC_THREADS=4` 可让内核并行处理独立样本，
合法线程数为 1–64；结果顺序和首个失败的样本下标不变。Rust 调用方可用
`run_with_threads(request, 4)`。瞬态仍按时间顺序推进；线程启动有开销，小批量未必更快。

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块依赖 IR 和表达式校验，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份沿用 v2；当前实现表达式、事件与算子使用 IR v18，序列化迁移规则见下文。

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
| 联合连续动态：[CONTINUOUS](docs/math/continuous.md) | [continuous.rs](rust_core/src/continuous.rs) 关系与 DC；[continuous_derivatives.rs](rust_core/src/continuous_derivatives.rs) 导数；[state_space.rs](rust_core/src/state_space.rs) 线性传播；[nonlinear_dynamics.rs](rust_core/src/nonlinear_dynamics.rs) 多项式传播；[implicit_dynamics.rs](rust_core/src/implicit_dynamics.rs) DAE；[continuous_initialization.rs](rust_core/src/continuous_initialization.rs) 联合冷启动；[guard_trajectory.rs](rust_core/src/guard_trajectory.rs) / [dynamic_roots.rs](rust_core/src/dynamic_roots.rs) 动态根 | [动态与生命周期](validation/DYNAMICS_CONTRACTS.md) | [连续关系](tests/test_continuous_dynamics.py)、[动态 cross](tests/test_dynamic_cross.py)、[动态组合](tests/test_dynamic_closure.py)、[混合算子](tests/test_mixed_dynamics.py)、[DAE](tests/test_implicit_dynamics.py) |
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

当前实现使用 IR v18，新增受限 driven 输入比较初值，保留 v17 的保持状态控制 timer 与 v16 的 ddt、连续动态网络、动态 guard 及逐条贡献契约；每条贡献的 RHS 是带 `op` 标签的表达式，不含“直接写节点”指令。
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
这些检查不扩展端口别名、命名支路、电流贡献或更广层次结构的支持范围。

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

Program 和成功 Response 的 `schema_version` 均为 **18**，Python 适配器与 Rust 内核同步检查。
旧版本或未知整数版本先于载荷解码返回 `unsupported_ir_version`；版本缺失/错误类型及当前格式错误返回
`invalid_request`。Rust 库构造入口也检查版本。旧 IR 1–17 的 JSON 须从原始 VA 与 manifest 重新编译，不能只改版本号。
前端与内核须配套使用。IR18 将 `State.initial` 扩为有限常数或明确的 0/1 `select` 比较；
比较只适用于 real 状态，两侧限 ground/实际 driven 输入的仿射表达式。
初始化先于算子历史、守卫日程、首次电压求解和 t=0 事件；详见[初始化契约](docs/math/events.md#input-initialization)。
IR1–17 必须从原始 VA/manifest 重新编译，不原地改写历史 IR 或收据。

仓库冒烟 manifest 的默认范围为 `evas/validation/smoke/`。批量工具读取原 VA 和实例参数，写入新的 IR18，
保留每项 manifest/source SHA256 及失败诊断；原 IR、历史波形和收据不改写：

```sh
python3 scripts/recompile_evas_manifests.py --output runs/recompile-ir18
python3 scripts/recompile_evas_manifests.py --output runs/recompile-selected evas/validation/smoke/idt.json
```

默认六项当前会有上述三项准入拒绝，命令返回非零并保留另三项成功输出。
需要演示修正后的三条路径时，显式选择版本化 successor：

```sh
python3 scripts/recompile_evas_manifests.py --output runs/recompile-smoke-admission-v1 evas/tests/fixtures/smoke-admission-v1
```

输出目录必须不存在；部分失败返回非零，成功项仍保留。没有原始 VA/manifest 的旧 IR 无法凭改版本号迁移。

更严格的瞬态认证会改变部分接受范围：多项式非方阵在点输入也拒绝；仿射冗余关系必须
在误差映射的参数域上成立，不能只在某个状态点碰巧一致。通用 `real` 状态保留误差区间，交给电压、事件和历史消费者验收；
近零状态不再单独受纯相对预算限制，但后续放大仍可能使请求无法认证。静态 `solve` 仍是局部 Newton 验收，没有同等根前向误差证书。
这些是明确实现边界，详见[精度链与兼容性](../experiments/runs/parallel-gap-integration/REVIEW.md#precision-chain)。
旧归档使用对应提交的前端和内核复现；[历史 v9 迁移说明](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#ir-v8-migration)保留原身份。

`Program.states/events/operators` 为空时保持静态语义；省略这些字段也只表示空列表，不推断事件。
`state` 表达式保存状态索引，状态含实例身份、名称、类型及初始化常数或上述输入比较；事件为 `trigger/body/origin`。
body 的 `kind=assign` 含 `state/rhs`；`kind=if` 含 `relation/left/right/then_body/else_body/origin`，
relation 为 `lt/le/gt/ge`。无 else 序列化为空 body；未知字段、关系或缺失 body 均拒绝。
trigger 支持 cross、固定及保持状态控制的 timer，以及 cross/timer 混合 OR；格式、身份与事件记录见[事件手册](docs/math/events.md#event-or)。
源码 `timer(start)` 为单次事件，`timer(start,period)` 为周期事件；省略的时间容差采用 EVAS 的
`1e-12 s` 默认值。该值不是与 Spectre 共享的默认设置；规则和拒绝边界见[固定 timer](docs/math/events.md#固定-timer)。
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

## 保存完整运行结果

使用 `python3 -m evas.results run MANIFEST --kernel PATH --out NEW_DIR` 保存带身份的完整 JSON、CSV 和源码快照。只有最后写入的 `manifest.json` 标记为 `complete` 才表示完整产物；失败保留诊断与部分文件。单位、精度、失败处理和使用示例见[运行产物契约](docs/reference/results.md)。
