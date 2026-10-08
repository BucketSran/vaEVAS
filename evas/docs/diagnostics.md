# 诊断与只读查询

执行诊断说明内核已经做了什么。只读查询不调用模型求值，不定位新事件，也不改变数值验收。
编译预检查单独报告已完成的静态检查，不表示执行受支持。
普通 `solve` / `transient` 的成功 JSON 格式沿用当前 IR17。

## 编译和执行失败

Python `CompileError.diagnostic` 与 `KernelError.diagnostic` 提供
`diagnostic_version=1`、`code`、`category`、`stage`、`capability` 和 `message`。
有准确来源时提供 `location`/`instance`；没有时不猜测。
CLI 在 stderr 输出同样的 JSON 并返回 2；命令参数错误也采用此边界，帮助文本保留 argparse 的成功退出。旧 `str(CompileError)` 及
`KernelError.detail` 保留原始信息；内核原有 kind/message/sample 字段继续可用。
诊断规范元数据覆盖同名载荷值时，`diagnostic.raw_payload` 保存完整原载荷，
包括载荷自己已有的 raw_payload 字段；规范 category/capability 仍按登记表或 unknown 生成。
该附加诊断版本独立于求解 IR，不要求迁移 IR17。

登记入口为 [errors.py](../src/evas/errors.py)。当前具名规则包括：

| code | 阶段与原因 |
| --- | --- |
| `undeclared_node` | lowering：完整电气声明环境中，电压访问引用未声明的节点；受限算子上下文仍 unknown，保留原 token 与绑定实例 |
| `duplicate_module` / `connection_mismatch` | parse/binding：重复模块定义，或实例端口/电气连接与声明不符 |
| `unsupported_timer_dependency` | lowering：timer 参数依赖连续电压或算子；不会误报未声明节点 |
| `manifest_input` / `manifest_io` | input：清单结构或编码错误；清单文件访问失败 |
| `source_input` / `source_io` | input：源文本编码错误；源文件访问失败 |
| `parameter_dependency` / `parameter_override` | binding：无效或循环参数默认值；未知、非数值或非有限的覆盖值 |
| `resource_budget` | compile：表达式、参数依赖或展开 IR 达到实现预算，不作为语言非法判断 |
| `parameter_type` / `parameter_range` | binding：整数子集限制，或生效值违反范围 |
| `unsupported_integer_arithmetic` | binding：受限前端入口中的整数除法或溢出不能用实数 IR 代替 |
| `vector_declaration` / `unsupported_vector` | binding：声明不一致，或超出静态向量子集 |
| `unsupported_initial_event` | 不支持的初始化生命周期、混合事件或初值表达式 |
| `unsupported_event_context` | binding：事件位于普通模拟条件下，需要尚未支持的运行时激活语义 |
| `scs_input` / `unsupported_scs` | netlist：非法测试台，或未支持的输入语义 |
| `kernel.unsupported_implicit_dynamics` | kernel：包括 DAE 与事件/状态尚未联合支持的情况 |

本 E1 切片把已审计的 token、宏/函数、genvar、层级与数组预算来源映射到已有
`resource_budget`；递归/未确定原因继续 unknown。内核 `nonconvergence` 为 numerical，
`event_budget` 为 resource，`input_io`、`diagnostic_io`、`worker_start` 为 infrastructure。
来源、实际触发、全源码观察与消费者兼容见[来源登记](diagnostic-sources.md)。
完整机器清单覆盖已审计工厂/包装/转换；不表示所有出口都实际触发，也没有交付外部 benchmark 消费适配。

其他内核 code 为 `kernel.<原 kind>`；已知 kind 按输入、版本、数值、协议、资源或
基础设施归类。已登记的具体原因保留已有分类，未登记的失败保持 `unknown`。
不会从 `unsupported_` 前缀或错误文字猜测分类。自由文本的旧编译出口也可返回
`unknown`；本批没有完成所有出口的细分类或外部 benchmark 适配。
编译成功不意味着执行或精度验收成功。回归见
[test_frontend_diagnostics.py](../tests/test_frontend_diagnostics.py)。

## 只编译的预检查

```sh
PYTHONPATH=evas/src python3 -m evas lint evas/examples/01-static-gain/sim.json
```

API 为 `evas.lint.lint_manifest(path)`。它读取清单和源文件，检查编译所需结构，
绑定参数并编译当前支持的源码，还检查展开 IR 的资源预算。它不发现、查询或
启动内核，机器没有安装内核也能运行。编译入口为
[evas/lint.py](../src/evas/lint.py)，CLI 分派为
[__main__.py](../src/evas/__main__.py)。

成功 JSON 使用 `lint_version=1` 和 `status=lint_passed`，`checks` 列出实际完成的
编译检查；`not_checked` 明示尚未检查数值请求有效性、动态执行支持、数值验收和
外部仿真器兼容性。刺激字段仍通过清单的基础结构解析，但 lint 不验证驱动节点、
样本数值或瞬态设置是否满足内核的数值请求契约。不会输出“仿真有效”或 benchmark 分数。

预检查成功可以随后执行失败。例如带 timer 修改状态的多项式 DAE 能完成编译，
当前内核仍返回 `unsupported_implicit_dynamics`，原因为
`index-one polynomial DAE currently requires an event-free network`。
该案例在改诊断前以现有真实内核冻结并验证，回归见
[test_lint.py](../tests/test_lint.py) 与已有 #69
[test_frontend_diagnostics.py](../tests/test_frontend_diagnostics.py)。timer 连续依赖
与 DAE/事件组合保留原来的 `unsupported` 分类和对应能力；其他额外内核载荷字段也保留。

## 来源盘点与覆盖边界

完整源码观察存于 [diagnostic-inventory.json](diagnostic-inventory.json)，由
`scripts/diagnostic_inventory.py` 生成并由 CI 检查新鲜度。它包含 Python 前端/CLI、Rust
生产源码和 IR 子 crate 的构造、包装、转换、处理器与元数据改写；以源码结构而非行号标识。
当前共 780 条源码观察，372 条仍为 unknown；这些数包括同一路径的多个观察，不是错误
种类数或执行覆盖率。完整范围、数量分组、未来维护边界和实际触发证据见[来源登记](diagnostic-sources.md)。

普通 manifest CLI、lint、results/capture 使用同一输入来源诊断。results 的 API、CLI 与失败
marker 保持相同 diagnostic；迁移结果保留旧文本 diagnostic，并附加 error。捕获会话保留
原内核 payload.error，另含 error_diagnostic；status/MCP status 传递两者。旧会话缺附加字段
时返回 null，不能解释为执行成功。明确非 v1 的内核诊断保留原版本和载荷，按 unknown
处理，不根据已知 kind 套当前类别。回归见 [消费者测试](../tests/test_diagnostic_consumers.py)。

已执行的来源负例与源码盘点分开报告；unknown 不表示候选模型非法，也不表示实现缺陷。
外部 benchmark/harness 的读取及评分分母验收仍待完成，因此 #64 总项继续开放。

## 取得一次运行

先构建内核，再对现有 manifest 生成独立会话文件：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
mkdir -p runs
PYTHONPATH=evas/src python3 -B -m evas.diagnostics capture evas/examples/02-integrator/sim.json --kernel evas/rust_core/target/debug/evas-kernel --out runs/session.json
```

manifest 仍列出 VA、平面实例、刺激和精度。会话绑定 manifest、VA 原字节、
编译 IR、请求、内核文件与 Python 前端的 SHA256。模型或内核在执行期间被替换时，
不保存为同一身份。会话保存成功响应，或内核失败及有限的诊断前缀。
SHA256 用于发现资产漂移，不是第三方执行证明。

Rust 调用者可使用 `evas_kernel::diagnostics::capture(Options, || run(request))`。
进程调用者设置 `EVAS_DIAGNOSTICS_PATH` 后，内核额外写 JSON sidecar。
路径必须尚不存在，父目录必须存在；已有记录不会被覆盖。
成功求解后写 sidecar 失败时进程以 3 退出，报告 `diagnostic_io`；
原有内核失败仍以 2 退出并保留原错误。中止、超时或不完整 JSON 不能作为完整轨迹。

## 记录内容与边界

- `event_batch/committed`：状态、历史、日程游标与事件记录已整批提交。
- `controller_step/committed`：控制器已接受一次推进。
- `time_proposal/discarded`：更早的已知事件取消了提议时间；不是数值求解失败。
- `nonlinear_candidate/certified` 或 `rejected`：候选中的积分小步及已有拒绝原因。
  候选内的小步认证不等于正式历史已提交。
- 阶段耗时与计数：分解、回代、原关系残差、历史查询/复制、认证、日程及传输。

计时是**包含子阶段的墙钟时间**，各项重叠，不能直接相加。稀疏 ordering 项只测取下一列；
活动集合/列度维护包含在 elimination 项中。`history_clone_operator_slots` 是复制对象中
的算子槽位数，**不是复制字节数或深拷贝内存量**。
收集器属于调用线程，静态并行工作线程内部不会被计数；`coverage` 明确写出该边界。
`matrix_rows`、`matrix_columns`、`matrix_input_nnz` 及 `sparse_lu_entries` 按每次分解累加，
是本次运行的工作量；只有一次分解时才分别等于该矩阵的尺寸/存储项，不能作为峰值维数或内存。

轨迹默认最多 2048 条、1 MiB 记录字节。`EVAS_DIAGNOSTICS_RECORDS` 和
`EVAS_DIAGNOSTICS_BYTES` 可设置预算；有效上限分别为 65536 条和 8 MiB；非法预算返回 `invalid_config`。
sidecar 报告有效预算、`record_bytes`、`dropped_records` 与 `truncated`。
预算针对轨迹记录，不包括响应、身份、汇总和原错误。截断不影响内核结果，
但不能据此声称完整观察了事件和试算。默认不启用诊断。
实际开销见[测量协议与结果](../../experiments/performance/README.md)。

## 静态与运行查询

```sh
PYTHONPATH=evas/src python3 -B -m evas.diagnostics query runs/session.json operators --limit 20
PYTHONPATH=evas/src python3 -B -m evas.diagnostics query runs/session.json trace --start 0 --limit 100
```

静态分区有 `modules`、`instances`、`nodes`、`contributions`、`operators`、`states`、`events`。
模块来自同一语法解析器；实例参数列是 manifest 的覆盖值。节点读依赖、支路、状态和
算子依赖来自编译 IR；源码行列来自编译器的 `Origin`，没有位置的对象不补猜测值。
索引只在绑定的 IR 内有效，贡献交换顺序可以改变索引，不能把它当跨版本身份。

运行分区有 `status`、`metrics`、`trace`、`samples`、`firings`。
每页最多 1000 项。`samples` 只返回已输出的点，不提供任意时刻的插值。
查询检查当前文件与绑定身份；manifest、VA、IR、前端、内核或会话漂移时拒绝旧会话。
会话需要原绑定文件仍可访问，不是自动跨机器搬移的归档格式。

## MCP 入口

```sh
PYTHONPATH=evas/src python3 -B -m evas.mcp runs/session.json
```

这是单会话、只读的 stdio 服务。工具调用只读上述数据，不启动仿真。
支持 `initialize`、`notifications/initialized`、`ping`、`tools/list` 与 `tools/call`；
协议版本为 `2025-11-25`。输出只含换行分隔的 JSON-RPC，输入与单次响应有 1 MiB 上限。
大页返回预算错误，调用方可减小 `limit`。EOF 结束服务；没有后台任务或 HTTP 服务。

`evas_why_no_cross` 返回已有 firing 计数，或 `unknown`。
目前没有完整的 guard 符号轨迹，因此“没有 firing”不能证明无根、方向不符或求解失败的具体原因。
失败、缺 sidecar、截断和源身份不一致也不能被解释为物理结论。

接口参考 [MCP stdio](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)、
[生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)和
[工具规范](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)。
[Tencent wave-mcp](https://github.com/Tencent/wave-mcp)提供了静态结构与运行数据分开查询的参考；
本实现不沿用其 RTL 波形逻辑，也不据此声称连续时间根或精度正确。
验证入口为 `test_query.py`、`test_diagnostics.py` 及 Rust 收集器/缓存测试。

`lint` 明确拒绝执行选项 `--kernel` 与 `--timeout`，返回 `input_error`；
不把这些选项静默忽略，也不把仅编译通过当作内核检查成功。

输入比较初始化的 Rust 拒绝为 `unsupported_initialization`（unsupported/LANG）；
输入包围不能证明分支时为 `initialization_precision`（numerical/LANG），消息包含源码和状态身份。
两者均先于模型/历史/接受帧构造，失败响应不含成功波形。来源见
[初始化契约](math/events.md#input-initialization)和[公开回归](../tests/test_input_initialization.py)。
