# 请求级资源上限：证明工作量与输出点数

两项上限都是实现预算，不是 Verilog-A 语言限制，也不是正确性判据或性能承诺。

## 源跳变证明工作量 `proof_work_limit`

源跳变证明账有三个槽，分别限制计划数、割点数和证明工作量；请求的账是 `[128, 8192, W]`。
账是粘性的：失败的预留不退还，共用一本账的消费者重试也不会重新获得额度。
消费者在已有所有者（源上下文、过程、解析源）时共用它的账，没有时用同一个 `W` 另建一本，
所以一个请求可以有几本账，例如事件账 `[128, 8192, W]` 和算子计划账 `[8192, 8192, W]`。
`proof_work_limit` 设置每本账的第三槽 `W`；槽 0 和槽 1、账本语义都不变。
唯一例外是 transition 输入取值形式的审计（`operators.rs` 的 `transition_input`）：每次调用另建缺省账
`[128, 8192, 1e9]`，不取 `W`。内核只接受不超过 100000 个 IR 值、容器深度不超过 96 的程序（`event_control::validate`），
据此每次审计最多约 6.9e6 工作量，远低于 1e9，所以调高 `W` 不需要作用于这本账。

| 项 | 取值 |
| --- | --- |
| 缺省 | `1_000_000_000`（`DEFAULT_PROOF_WORK_LIMIT`）；缺省时请求与以前逐字节相同，不发送该字段 |
| 硬上界 | `10_000_000_000_000`（`MAX_PROOF_WORK_LIMIT`，1e13）。这是防止误写的实现预算护栏，不是正确性判据，也不是性能承诺：一个工作量单位不等于固定时间，约在 0.4–1.2 ns 到数 ns 之间随模型变化 |
| 合法值 | 整数且 `1 <= 值 <= 1e13`。其他值按收到它的那一层拒绝：内核请求里，非正、超界、布尔、浮点（含 `2e12`、`2000000000000.0`）、字符串、JSON `null`、超出 u64 的整数一律是 `invalid_inputs`；CLI 清单里只要写了 `transient.proof_work_limit` 就必须是范围内的整数，`null` 和其他形态在发送前拒绝，诊断点名该字段；Python API 里 `None` 就是缺省、表示未设置（不发送该字段，请求字节与以前相同），其他非整数或超界值在发送前报 `ValueError` |
| 回显 | 响应 `observation_evidence.effective_controls.proof_work_limit` 总是回显实际生效的上限，包括缺省的 `1000000000` |

使用方式：

- Python：`runtime.transient(..., proof_work_limit=N)` 和 `scs.simulate_scs(path, proof_work_limit=N)`；`proof_work_limit=None`（缺省）表示未设置。
- CLI：`python -m evas simulate TB.scs --proof-work-limit N`；`transient` 也接受，且清单里同时写了该字段时拒绝。`N` 只能是十进制数字（拒绝 `1e9`、`+5`、`1.5`）。其他动作不接受该选项。
- CLI 清单：`transient.proof_work_limit` 省略即缺省；写了就必须是 `1..1e13` 的整数。清单里的 `null` 不等于未设置，与其他非法值一样在读取清单时拒绝（`manifest_input`），不会静默改用缺省。

账本按序列化请求字节收费，所以同一模型的总工作量不是纯函数：源文件的绝对路径出现在 IR 的来源字段里，
路径每多一个字符，在已测的四个用例里总量增加约 1.4e5（slot 19）到 1.0e7（slot 1）单位。
确定性只对同一请求字节成立；选择上限时需要留出余量。限制值本身不参与收费（它不序列化进配置身份）。

响应校验（`protocol.validate_response(..., proof_work_limit=)`）：请求设置了上限时，回显必须存在且相等；
未设置时回显必须是缺省值。没有该回显的旧内核仅在请求未设置上限时被接受，因为旧内核会拒绝这个字段。

兼容性：请求字段在 `deny_unknown_fields` 下，旧内核会以 `invalid_request` 明确拒绝它。
本改动没有提升 `request_protocol_version`（仍为 null）；是否需要版本化记为后续问题。

调大上限只改变预算，不改变数值判据。大账本和大网格运行时间长，调用方须显式调大 `timeout`
（`runtime.DEFAULT_TIMEOUT` 是 300 s，CLI 用 `--timeout`）。

## 输出点数 `MAX_OUTPUT_POINTS`

SCS 输出网格、源折点并入后的行、保存行、周期与显式 strobe、脉冲角数以及响应的 `strobe_evidence.times`
共用 `evas.limits.MAX_OUTPUT_POINTS = 1_000_000`；Rust 内核在 `ir` crate 定义同值的
`MAX_OUTPUT_POINTS` 并用它检查强制点数（Python 与 Rust 的一致性由测试核对）。
`scs_sources.POINT_BUDGET` 与 `strobe.MAX_POINTS` 保留旧名，值等于该常量。
错误消息由实际生效的限制生成。

SCS 网格的准入条件是 `floor(stop/maxstep) + 2 <= 限制`；当 `stop/maxstep` 恰为整数时实际行数为
`floor(stop/maxstep) + 1`，该条件偏保守一行。脉冲角数按 `4*周期数 + 2` 计。
这些常数不改变网络表 token 上限（`scs.py`）和其他同数字的无关预算。
