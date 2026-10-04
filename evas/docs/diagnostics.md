# 诊断与只读查询

诊断说明内核已经做了什么。它不调用模型求值，不定位新事件，也不改变数值验收。
普通 `solve` / `transient` 的成功 JSON 格式沿用当前 IR17。

## 编译和执行失败

Python `CompileError.diagnostic` 与 `KernelError.diagnostic` 提供
`diagnostic_version=1`、`code`、`category`、`stage`、`capability` 和 `message`。
有准确来源时提供 `location`/`instance`；没有时不猜测。
CLI 在 stderr 输出同样的 JSON 并返回 2。旧 `str(CompileError)` 及
`KernelError.detail` 保留原始信息；内核原有 kind/message/sample 字段继续可用。
该附加诊断版本独立于求解 IR，不要求迁移 IR17。

登记入口为 [errors.py](../src/evas/errors.py)。当前具名规则包括：

| code | 阶段与原因 |
| --- | --- |
| `unsupported_timer_dependency` | lowering：timer 参数依赖连续电压或算子；不会误报未声明节点 |
| `parameter_type` / `parameter_range` | binding：整数子集限制，或生效值违反范围 |
| `unsupported_integer_arithmetic` | binding：受限前端入口中的整数除法或溢出不能用实数 IR 代替 |
| `vector_declaration` / `unsupported_vector` | binding：声明不一致，或超出静态向量子集 |
| `unsupported_initial_event` | parse：缺少所需分析生命周期或混合全局/监测事件 |
| `unsupported_event_context` | binding：事件位于普通模拟条件下，需要尚未支持的运行时激活语义 |
| `scs_input` / `unsupported_scs` | netlist：非法测试台，或未支持的输入语义 |
| `kernel.unsupported_implicit_dynamics` | kernel：包括 DAE 与事件/状态尚未联合支持的情况 |

其他内核 code 为 `kernel.<原 kind>`；已知 kind 按输入、版本、数值、协议、资源或
基础设施归类。`unsupported_*` 标记实现范围，未登记的失败保持 `unknown`。
自由文本的旧编译出口也可返回 `unknown`；本批没有完成所有出口的细分类、lint 或 benchmark 适配。
编译成功不意味着执行或精度验收成功。回归见
[test_frontend_diagnostics.py](../tests/test_frontend_diagnostics.py)。

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
