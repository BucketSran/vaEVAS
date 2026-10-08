# 外部诊断消费移交

本文件记录 #64 尚未完成的 Circuit Harness 依赖，不代表已实现外部适配。
本库版本化协议为 [诊断合同](diagnostics.md)，实际触发用例为
[test_diagnostic_sources.py](../tests/test_diagnostic_sources.py)；源码观察数量由
[机器清单](diagnostic-inventory.json) 提供，不能充当错误种类数或执行覆盖率。

## 已检查的消费点

2026-10-08 只读检查 Circuit Harness 的 `demo/chips`，固定源码身份
`66c451ff2ce3642df4436e73fccc2bc5a9579a18`。实际本地项目来自 Codex 配置的 Circuit Harness。
没有修改该项目、运行其容器/模拟器或声称外部验收通过。

- `alphaapollo/common/execution/chips/current_evas_public.py` 的 `run_public`
  在非零退出时生成 `execution=backend_error`；随后从 `evas.stderr.log` 只取末尾 4000 字符，
  脱敏后写入 `result.json` 的字符串 `diagnostics`。未解析 diagnostic_version、category、code、stage。
- `alphaapollo/common/execution/chips/current_evas_session.py` 的 `_finish_simulation`
  按任务 `feedback_fields` 投影结果。允许的反馈字段为 diagnostics/observations，新增机器字段还需
  明确兼容或版本化；仅在执行层新增字段不能证明已通过公开会话传递。
- `alphaapollo/common/execution/chips/benchmark_replay.py` 的 `summarize_replays`
  先验证每份 receipt，再累计所有 records，包含 infra/unevaluable/not_compared 等失败。
  这项失败分母契约必须保留，分类不得成为丢弃 record 的条件。

公开文本和机器消费需各自保留契约。末尾截断可能破坏完整 JSON；不能把截断字符串解析失败
解释为候选模型失败。机器解析应使用未截断的完整 stderr 或版本化错误文件，原日志继续保留。
脱敏需作用于公开字段，内部原始诊断与有效设置保留在原记录中。

## 拥有者与待交付验收

责任组件是 Circuit Harness 的当前 EVAS 执行与 benchmark/replay 适配。下一次独立任务在其
项目中实现，不在 vaEVAS 的 benchmark 定义或 Rust 数值内核中复制执行编排。
尚无新建的外部 Issue/PR 身份，本入口保留 #64 依赖；创建外部任务后应补入其固定链接。

适配必须显式处理 `diagnostic_version=1`。非 v1、无诊断或损坏/截断载荷的类别保持 unknown，
保留原版本与原载荷；不能用已知 kind 或文字反套当前规则。协议字段缺失不代表执行成功。
category 是失败原因，不是支持认证等级或自动缺陷判断。`execution=backend_error` 可保持兼容，
结构化分类作为附加证据传递，评分判决仍由原 checker 作出。

至少完成以下消费端到端验收，固定候选集合和原失败分母，同时检查内部记录与公开投影。

| 输入 | 诊断期望 | 消费与评分义务 |
| --- | --- | --- |
| timer 参数 `V(u,r)`，u/r 已声明 | v1 / unsupported_timer_dependency / lowering / unsupported / TIMER | 区分范围边界，保留原位置和 message；记录仍在分母 |
| 事件修改积分导数的多项式 DAE | lint_passed，随后 kernel.unsupported_implicit_dynamics / kernel / unsupported / DYNAMICS | 静态预检成功不能当作动态运行成功；记录仍在分母 |
| `V(y,r)<+pow(V(u,r),3)`，u=1e200 | kernel.nonfinite_arithmetic / kernel / numerical | 有限输入引发运算溢出，不自动确认实现 bug；原 sample 和失败保留 |
| integer n=2147483647，t=0 timer 执行 n=n+1 | kernel.state_range / kernel / unsupported | 明确 EVAS 32 位实现边界，不与数值溢出混为一类 |
| 源文件不可读或模拟器启动失败 | infrastructure 或执行层 infrastructure_error | 保留真实来源与有效设置，不算候选语义错误；记录仍在分母 |
| 非 v1 / 无诊断 / 损坏载荷 | unknown，原版本/日志保留 | 不套用 v1 kind 映射，不丢失败，不解释为成功 |

先校准构造载荷的接受/拒绝边界，再至少运行真实当前 EVAS 的上述编译与内核失败，通过
执行层、公开 session 和 replay receipt 汇总路径。构造 CLI/Docker 夹具不替代真实 EVAS 消费验收。
记录实际 EVAS 源码、内核 SHA-256、IR 与诊断版本及 harness revision，报告该固定集合的
全部执行结果。此依赖完成前，#64 外部消费验收继续待办。
